"""sl_board - the SL Dashboard's arithmetic (28-Oct-2026)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sl_board as sb  # noqa: E402


def test_thesis_is_judged_on_the_close():
    assert sb.thesis_state(99.0, 100.0, 4.0) == "BROKEN"
    assert sb.thesis_state(101.0, 100.0, 4.0) == "NEAR"      # within 0.5 x ATR
    assert sb.thesis_state(110.0, 100.0, 4.0) == "ok"
    assert sb.thesis_state(110.0, None, 4.0) == ""


def test_risk_numbers_loss_open_risk_and_the_share_count_that_fits():
    # 100 sh, cost 200, LTP 180, stop 150: loss from cost 5,000; open risk 3,000;
    # a 2,500 rule fits 50 shares at that stop
    loss, open_r, fit = sb.risk_numbers(100, 200.0, 180.0, 150.0, 2500.0)
    assert (loss, open_r, fit) == (5000.0, 3000.0, 50)


def test_a_stop_above_cost_locks_profit_and_needs_no_trim():
    loss, open_r, fit = sb.risk_numbers(10, 100.0, 150.0, 120.0, 1000.0)
    assert loss < 0 and open_r == 300.0 and fit is None


def test_axis_in_atr_and_percent():
    r = {"ltp": 200.0, "atr": 10.0}
    assert sb.to_axis(r, 170.0, "atr") == -3.0
    assert abs(sb.to_axis(r, 220.0, "pct") - 10.0) < 1e-9
    assert sb.to_axis(r, None, "atr") is None
    assert sb.to_axis({"ltp": 200.0, "atr": None}, 170.0, "atr") is None


def test_triage_order_thesis_first_then_trail_orders_rule_noise():
    assert sb.triage({"thesis_state": "BROKEN", "chand_breach": True})[0] == 0
    assert sb.triage({"chand_breach": True, "over_budget": True})[0] == 1
    assert sb.triage({"order_warn": "20 of 50 shares have no stop", "over_budget": True})[0] == 2
    assert sb.triage({"over_budget": True, "noise": "red"})[0] == 3
    assert sb.triage({"noise": "red"})[0] == 4
    assert sb.triage({"thesis_state": "NEAR"})[0] == 5
    assert sb.triage({})[0] == 9


def test_every_level_has_a_column_in_the_frame():
    # the chart draws sb.LEVELS by key; build() must emit each key
    import inspect
    src = inspect.getsource(sb.build)
    for key, *_ in sb.LEVELS:
        if key == "avg" or key == "ltp":
            continue
        assert f'"{key}":' in src, key


# ── gap risk, stop history, edits (28-Oct-2026) ─────────────────────────────────────────
import sqlite3  # noqa: E402

import pandas as pd  # noqa: E402

import gap_risk as gr  # noqa: E402
import stop_history as sh  # noqa: E402


def test_gap_stats_reads_open_vs_previous_close():
    close = [100.0] * 80
    opens = [100.0] * 80
    opens[50] = 90.0                       # one -10% gap
    df = pd.DataFrame({"Open": opens, "Close": close},
                      index=pd.date_range("2025-01-01", periods=80, freq="B"))
    g = gr.gap_stats(df)
    assert round(g["gap_worst"], 6) == -10.0 and g["gaps_3pct"] == 1
    assert g["gap_worst_date"] == df.index[50].strftime("%Y-%m-%d")


def test_a_gap_above_the_stop_fills_at_the_stop_and_below_it_at_the_open():
    assert gr.gap_fill(100.0, 90.0, -5.0) == 90.0            # opens 95, stop still holds
    assert abs(gr.gap_fill(100.0, 90.0, -15.0) - 85.0) < 1e-9  # opens 85, through the stop
    fill, loss, fit, through = gr.gap_numbers(10, 100.0, 100.0, 90.0, -15.0, 100.0)
    assert through and abs(loss - 150.0) < 1e-9 and fit == 6


def test_events_find_widening_and_tightening_with_rupees():
    df = pd.DataFrame([
        {"date": "2026-10-01", "symbol": "X", "qty": 100, "avg": 200, "disaster": 180, "thesis": 190, "source": "backup"},
        {"date": "2026-10-02", "symbol": "X", "qty": 100, "avg": 200, "disaster": 170, "thesis": 190, "source": "backup"},
        {"date": "2026-10-03", "symbol": "X", "qty": 100, "avg": 200, "disaster": 175, "thesis": 185, "source": "dhan"},
        {"date": "2026-10-03", "symbol": "X", "qty": 100, "avg": 200, "disaster": 999, "thesis": 999, "source": "backup"},
    ], columns=sh.COLS)
    ev = sh.events(df)
    kinds = list(ev["kind"])
    assert kinds == ["WIDENED", "TIGHTENED", "THESIS ↓"]       # the dhan row wins over the backup on 10-03
    assert ev.iloc[0]["rupees"] == 1000.0 and ev.iloc[0]["below_entry"]
    s = sh.summary(ev, open_syms=["X"])
    assert s.iloc[0]["widened"] == 1 and s.iloc[0]["risk_added"] == 1000.0


def test_save_edits_writes_thesis_backs_up_logs_history_and_keeps_plans_out_of_the_journal(tmp_path, monkeypatch):
    import journal_path as jp
    db = tmp_path / "trade_journal_v6.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE journal (symbol TEXT, status TEXT, quantity REAL, buy_price REAL, "
                "stoploss REAL, thesis_sl REAL)")
    con.execute("INSERT INTO journal VALUES ('ABC','OPEN',100,200,170,180)")
    con.commit(); con.close()
    monkeypatch.setattr(jp, "JOURNAL_DB", str(db))
    res = sb.save_edits([{"symbol": "ABC", "thesis": 185.0, "qty": 100, "avg": 200, "disaster": 170},
                         {"symbol": "ABC", "plan_qty": 60, "note": "trim"}])
    assert res["thesis"] == 1 and res["plan"] == 1 and not res["errors"]
    assert os.path.exists(res["backup"])
    con = sqlite3.connect(db)
    th, q, st = con.execute("SELECT thesis_sl, quantity, stoploss FROM journal").fetchone()
    con.close()
    assert th == 185.0 and q == 100 and st == 170           # quantity and the Dhan stop untouched
    assert sb.load_plans()["ABC"]["plan_qty"] == 60
    assert sh.load()["source"].tolist() == ["page"]
    sb.save_edits([{"symbol": "ABC", "plan_qty": None, "note": ""}])
    assert "ABC" not in sb.load_plans()                     # cleared plan leaves nothing behind

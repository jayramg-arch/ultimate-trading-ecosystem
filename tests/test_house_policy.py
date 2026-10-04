"""house_policy (25-Sep-2026): one home for risk %, capital, caps and the bear rule.

Two kinds of test: the rules themselves, and GUARDS that fail if a surface grows its
own copy again - the drift the integration audit found (five sizers, four risk rates,
an invented ₹50L capital, a 39-day-stale hand-typed RRG flag feeding Risk Shield).
"""
import json
import os
import re

import house_policy as hp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _app_src():
    """The whole app: the router, the moved helpers and every page file (25-Sep split).
    Scanning only the router would pass while guarding nothing."""
    import glob
    parts = [_src("weinstein_commander_web_v4.0.py"), _src("commander_core.py")]
    for p in sorted(glob.glob(os.path.join(ROOT, "commander_pages", "*.py"))):
        parts.append(open(p, encoding="utf-8").read())
    return "\n".join(parts)


def test_risk_rates_are_the_dna():
    assert hp.RISK_NEW_STOCK_PCT == 0.5
    assert hp.RISK_NEW_ETF_PCT == 0.75
    assert hp.RISK_ADD_PCT == 1.0
    assert hp.risk_pct_for("TITAN") == 0.5
    assert hp.risk_pct_for("TITAN", add=True) == 1.0


def test_bear_rule_treats_zero_as_bear_and_unknown_as_unknown():
    # exit_signal_engine used `score or 10`, which made a score of 0 read as NOT bear.
    assert hp.is_bear(0) is True
    assert hp.is_bear(5) is True
    assert hp.is_bear(6) is False
    assert hp.is_bear(None) is False
    assert hp.is_bear("nan") is False


def test_sizing_capital_never_invents_a_number(tmp_path, monkeypatch):
    p = tmp_path / "gm_settings.json"
    p.write_text(json.dumps({"capital": 0}))
    monkeypatch.setattr(hp, "_GM_SETTINGS", str(p))
    cap, src = hp.sizing_capital()
    assert cap == 3_000_000 and src == "house default"   # Jay's ₹30L, never ₹50L
    p.write_text(json.dumps({"capital": 3000000, "max_alloc": 0}))
    assert hp.sizing_capital() == (3000000.0, "gm_settings")
    assert hp.max_alloc() == hp.MAX_ALLOC_DEFAULT  # 0 means the house cap, never uncapped
    qty, note = hp.size_qty("TITAN", 4831.0, 4748.1)
    assert qty == 20 and "alloc-capped" in note    # ₹15,000 risk wants 180; ₹1L cap binds


def test_order_gate_defaults_come_from_house_policy():
    import pre_trade_gate as ptg
    for name in ("MAX_OPEN_POSITIONS", "SECTOR_CAP_PCT", "MAX_RISK_PCT"):
        if not (os.getenv(f"PRETRADE_{name}") or os.getenv(f"WEBHOOK_{name}")):
            assert getattr(ptg, name) == getattr(hp, name), name


def test_no_surface_hardcodes_a_retired_risk_rule():
    web = _app_src()
    assert "size at 0.25% risk" not in web
    assert 'key="sniper_risk_pct"' not in web
    assert "rs_risk_budget_pct" not in web
    assert "5_000_000" not in web
    assert "value=5000, step=500" not in web       # the old flat ₹5,000 proposer risk
    cq = _src("capital_queue.py")
    assert not re.search(r"risk_pct\"\)|pyr_risk_pct\"\)", cq)


def test_manual_rrg_flag_is_fully_retired():
    for f, s in (("app", _app_src()), ("gm_trigger_board.py", _src("gm_trigger_board.py")),
                 ("capital_queue.py", _src("capital_queue.py"))):
        assert "rrg_load(" not in s and "rrg_save(" not in s, f
        assert "s4_rrg_lists(" not in s, f


def test_rrg_live_returns_quadrant_and_verdict_shape():
    import gm_trigger_board as g
    out = g.rrg_live(None)                         # too little data -> unknown, not a verdict
    assert out == {"quadrant": None, "tradeable": None}


# ── AUD-OCT-02 (4-Oct-2026): stop rules have one home ─────────────────────────────
def test_stop_rules_values():
    assert hp.POS_STOP_FLOOR_ATR_D == 4.0
    assert hp.CHANDELIER_MULT == {"POS": 4.5, "WYC": 3.5, "REV": 2.5, "SWG": 1.5}
    assert (hp.NOISE_ATR_RED, hp.NOISE_ATR_AMBER, hp.AT_SL_ATR) == (1.5, 2.0, 1.5)
    assert [hp.noise_band(x) for x in (1.0, 1.7, 3.0, None)] == ["red", "amber", "green", ""]


def test_stop_consumers_read_house_policy():
    import commander_core, risk_common
    assert commander_core.POS_STOP_FLOOR_ATR_D is hp.POS_STOP_FLOOR_ATR_D
    assert risk_common.trail_mult_for("POS-BO", False) == (4.5, "POS")
    assert risk_common.trail_mult_for("SWG-PB", True) == (2.0, "SWG")
    assert risk_common.trail_window_for("SWG-PB") == 14 and risk_common.trail_window_for("POS-BO") == 22


def test_no_private_copies_of_the_noise_or_at_sl_rule():
    pat = re.compile(r"\b(1\.5|2\.0)\s*\*\s*atr(14)?\b")
    for f in ("journal_page.py", "ai_risk_manager.py", "pyramid_logic.py"):
        hits = [l for l in _src(f).splitlines() if pat.search(l) and not l.lstrip().startswith("#")]
        assert not hits, (f, hits)


def test_holding_chandelier_matches_chandelier_exit_and_floor():
    """4-Oct-2026: the function Risk Shield and the v67 push share."""
    import numpy as np, pandas as pd, risk_common as rc
    n = 260
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    c = pd.Series(np.linspace(100, 200, n), index=idx)
    df = pd.DataFrame({"Open": c, "High": c + 2, "Low": c - 2, "Close": c})
    j = {"setup": "", "timeframe": "Swing", "buy_price": 150.0, "stoploss": 140.0}
    hc = rc.holding_chandelier(df, j, bear=True)
    lvl, m, _ = rc.chandelier_exit(df["High"], df["Low"], df["Close"], setup="", bear=True,
                                   above200=True, swing=True)
    assert hc["window"] == 14 and hc["mult"] == m == 2.0 and abs(hc["level"] - lvl) < 1e-9
    hi_floor = lvl + 5
    assert rc.holding_chandelier(df, {**j, "manual_sl_override": hi_floor}, bear=True)["level"] == hi_floor
    assert rc.holding_chandelier(df, {**j, "manual_sl_override": 10.0}, bear=True)["level"] == lvl
    assert rc.holding_chandelier(df, {**j, "manual_sl_override": 10.0}, bear=True, override_mode="Exact")["level"] == 10.0
    assert rc.holding_chandelier(df, j, bear=True, cap_protect=True)["mult"] == 2.5

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

"""The GM sizer must compute S4's dynamic risk, not a second number.

Each case is the formula in S4 (f_fold3889, ~:4219-4245) worked by hand. The first is the
live ACUTAAS panel of 24-Sep-2026, which printed "Qty @ 0.19% risk" on a 0.5% base.
"""
import s4_sizing as s


def test_acutaas_panel_reproduces():
    r = s.dynamic_risk(0.5, mkt_health=False, s2_structure=True, rs_up=False,
                       rv=0.61, atr_pct=4.1)
    assert round(r["active_pct"], 2) == 0.19


def test_bull_tape_full_conviction_scales_up():
    r = s.dynamic_risk(0.5, mkt_health=True, s2_structure=True, rs_up=True, rv=1.5, atr_pct=2.0)
    assert r["kelly_pts"] == 3 and r["active_pct"] == 0.5 * 1.25


def test_regime_discount_is_floored_at_quarter_base():
    r = s.dynamic_risk(0.25, mkt_health=False, s2_structure=False, rs_up=False, rv=None, atr_pct=1.0)
    assert r["regime_risk"] == 0.0625          # max(0.25 - 0.25, 0.25 * 0.25)


def test_final_floor_is_quarter_base():
    r = s.dynamic_risk(0.5, mkt_health=False, s2_structure=False, rs_up=False, rv=0.3, atr_pct=12.0)
    assert r["active_pct"] >= 0.125


def test_wcl_terms_mirror_s4():
    up = s.dynamic_risk(0.5, mkt_health=True, s2_structure=True, rs_up=True, rv=1.5, atr_pct=2.0,
                        setup_s2=True)
    down = s.dynamic_risk(0.5, mkt_health=True, s2_structure=True, rs_up=True, rv=1.5, atr_pct=2.0,
                          choch_count_20=2)
    assert up["kelly_mult"] == 1.5 and down["kelly_mult"] == 1.0


def test_rv_is_prior_50_bars_not_including_current():
    import pandas as pd
    v = [100.0] * 50 + [250.0]
    f = pd.DataFrame({"Volume": v})
    assert s.s4_rv(f) == 2.5

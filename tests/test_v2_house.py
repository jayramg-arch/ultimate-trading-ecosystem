"""v2 house rules (PREREG_v2_house_rules): schedule, tiers, tax netting."""
import datetime as dt

import pandas as pd

import v2_house as vh


def _d(s):
    return pd.Timestamp(s)


def test_wednesday_rule_normal_week():
    # Tue 20-Oct-2026 close decides, Wed 21 fills
    assert vh.is_wed_decision(_d("2026-10-20"), _d("2026-10-21"))
    assert not vh.is_wed_decision(_d("2026-10-19"), _d("2026-10-20"))   # Mon -> Tue
    assert not vh.is_wed_decision(_d("2026-10-21"), _d("2026-10-22"))   # Wed -> Thu
    assert not vh.is_wed_decision(_d("2026-10-23"), _d("2026-10-26"))   # Fri -> Mon


def test_wednesday_rule_holidays():
    assert vh.is_wed_decision(_d("2026-10-19"), _d("2026-10-21"))       # Tue holiday: Mon decides
    assert vh.is_wed_decision(_d("2026-10-16"), _d("2026-10-21"))       # Mon+Tue holiday: Fri decides
    assert vh.is_wed_decision(_d("2026-10-20"), _d("2026-10-22"))       # Wed holiday: Tue decides, Thu fills


def test_decision_days_one_per_week():
    idx = pd.bdate_range("2026-01-05", "2026-03-27")
    dd = vh.decision_days(idx, True)
    assert len(dd) == 12 and all(d.weekday() == 1 for d in dd)


def test_tiers_from_house_policy():
    assert vh.tier(1)["new_ok"] is False
    t = vh.tier(4)
    assert t["new_ok"] and t["risk_mult"] == 0.5 and abs(t["cap"] - 0.70) < 1e-9
    t = vh.tier(7)
    assert t["new_ok"] and t["risk_mult"] == 1.0 and t["cap"] is None
    assert vh.tier(None)["new_ok"] is False                          # unknown -> strictest


def _ctx(score, up200):
    d = _d("2026-10-16")
    cols = ["AAA", "BBB", "GLDX", "IDXE"]
    row = lambda v: pd.DataFrame([v], index=[d], columns=cols)
    g = {"sma100": row([90, 90, 90, 90]), "sma200": row([80, 80, 80, 120]), "gap90": row([False] * 4),
         "liq": row([True] * 4), "atr20": row([2.0, 2.0, 1.0, 1.0]), "b_up200": pd.Series({d: up200})}
    for lb in (60, 90, 120):
        g["clenow%d" % lb] = row([0.9, 0.5, 0.8, 0.7])
    f = {"has": row([True, True, False, False]), "atr": row([2.0, 2.0, 1.0, 1.0])}
    meta = {"GLDX": {"asset_class": "COMMODITY", "underlying": "Gold"},
            "IDXE": {"asset_class": "SECTOR", "underlying": "Nifty IT"}}
    return d, {"C": row([100, 100, 100, 100]), "g": g, "f": f, "stocks": ["AAA", "BBB"], "etfs": ["GLDX", "IDXE"],
               "etf_meta": meta, "etf_has": row([True] * 4), "etf_turn": row([1e9] * 4),
               "fno": lambda _d: {"BBB"}, "score": lambda _d: (score, {})}


def test_bear_tier_blocks_indian_buys_but_not_gold():
    d, ctx = _ctx(score=1, up200=False)
    r = vh.decide(d, ctx, vh.FULL, 1_000_000, 1_000_000, {}, 1)
    kinds = {s: k for s, _a, k in r["buys"]}
    assert "AAA" not in kinds and "BBB" not in kinds and "IDXE" not in kinds
    assert kinds.get("GLDX") == "etf"          # gold above its own 200-DMA, full risk (18-Oct fix)
    assert dict((s, a) for s, a, _k in r["buys"])["GLDX"] > 0


def test_nav_premium_takes_an_etf_out_of_the_pool_and_sells_a_holding():
    d, ctx = _ctx(score=1, up200=False)
    ctx["prem_ok"] = lambda s: (False, 53.8, "53.8% premium vs NAV") if s == "GLDX" else (True, 0.2, "")
    held = {"GLDX": {"sh": 100.0, "entry": 90.0, "entry_date": _d("2026-06-01"), "last": 100.0, "kind": "etf"}}
    r = vh.decide(d, ctx, vh.BOOK_FLAGS["V2H"], 1_000_000, 900_000, held, 1)
    assert "GLDX" in r["sells"] and "GLDX" in r["etf_premium_out"]
    assert not any(s == "GLDX" for s, _a, _k in r["buys"])
    r = vh.decide(d, ctx, vh.BOOK_FLAGS["V2H"], 1_000_000, 1_000_000, {}, 1)
    assert not r["buys"]


def test_fno_first_inside_the_cut_and_half_risk_in_neutral():
    d, ctx = _ctx(score=4, up200=True)
    vh_top = vh.H["top_pct"]
    vh.H["top_pct"] = 1.0                        # both stocks inside the cut
    try:
        r = vh.decide(d, ctx, vh.FULL, 1_000_000, 1_000_000, {}, 1)
    finally:
        vh.H["top_pct"] = vh_top
    stock_buys = [(s, a) for s, a, k in r["buys"] if k == "stock"]
    assert [s for s, _ in stock_buys] == ["BBB", "AAA"]          # F&O name first despite the lower rank
    assert abs(stock_buys[0][1] - 1_000_000 * 0.0005 / 2.0 * 100) < 1e-6   # 0.05 % per ATR in NEUTRAL


def test_fy_tax_netting():
    r = [(_d("2025-05-01"), 100.0, False), (_d("2025-06-01"), -40.0, False), (_d("2025-07-01"), 50.0, True)]
    t = vh.fy_tax(r)
    assert abs(t.iloc[0] - (0.20 * 60 + 0.125 * 50)) < 1e-9
    # an ST loss larger than ST gains sets off the LT gain in the same year
    t = vh.fy_tax([(_d("2025-05-01"), -80.0, False), (_d("2025-07-01"), 50.0, True)])
    assert abs(t.iloc[0]) < 1e-9
    # the remaining ST loss is carried into the next FY
    t = vh.fy_tax([(_d("2025-05-01"), -80.0, False), (_d("2025-07-01"), 50.0, True), (_d("2026-05-01"), 100.0, False)])
    assert abs(t.iloc[1] - 0.20 * 70) < 1e-9
    # an LT loss never offsets ST gains
    t = vh.fy_tax([(_d("2025-05-01"), 100.0, False), (_d("2025-06-01"), -30.0, True)])
    assert abs(t.iloc[0] - 20.0) < 1e-9


def test_v2h_amended_without_tiers_and_fno():
    # 18-Oct-2026 (Jay): the live V2H drops the exposure tiers and F&O priority; the registered set
    # stays reproducible for the record.
    f = vh.BOOK_FLAGS["V2H"]
    assert f["tiers"] is False and f["fno"] is False
    assert f["stop"] and f["wed"] and f["taxtrim"] and f["etf"]
    assert vh.V2H_REGISTERED == vh.FULL

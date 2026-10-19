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
    assert f["wed"] and f["taxtrim"] and f["etf"]
    # PREREG_v2_borrowed_rules: adopted sector / corr / poscap; rejected stage / heat / maxpos
    assert f["sector"] and f["corr"] and f["poscap"]
    assert not (f.get("stage") or f.get("heat") or f.get("maxpos"))
    # Jay 19-Oct-2026: Clenow's exits - no stop, no trail - and the twice-monthly reset, +/-10 % band
    assert not f["stop"] and not f["trail"] and not f.get("topup")
    assert f["reb2"] and f["reb_band"] == 0.10
    assert vh.BOOK_FLAGS["V2H"] is vh.V2H_CLENOW
    assert vh.V2H_REGISTERED == vh.FULL


def test_v2_rupees_use_indian_grouping():
    import p1_paper as pp
    assert pp._inr(1000000) == "₹10,00,000"
    assert pp._inr(30000000) == "₹3,00,00,000"
    assert pp._inr(-1234.4) == "-₹1,234"


def _panel(closes: dict, bench) -> dict:
    idx = pd.bdate_range("2020-01-01", periods=len(bench))
    C = pd.DataFrame(closes, index=idx)
    return {"Close": C, "High": C * 1.01, "Low": C * 0.99, "bench": pd.Series(bench, index=idx)}


def test_template_table_leader_scores_8_laggard_fails_rs():
    import numpy as np
    n = 400
    bench = 100 * 1.0005 ** np.arange(n)                 # index drifts up
    up = 100 * 1.003 ** np.arange(n)                     # leader: steady uptrend, outruns the index
    lag = 100 * 1.0002 ** np.arange(n)                   # rising but lags the index
    T = vh.template_table(_panel({"UP": up, "LAG": lag}, bench), ["UP", "LAG"])
    assert int(T["UP"].iloc[-1]) == 8
    assert int(T["LAG"].iloc[-1]) <= 7                    # RS fails (and the 30 %-off-low test)
    assert int(T["UP"].iloc[100]) < 8                     # not enough history for SMA200 yet


def test_template_gap_day_does_not_blank_the_window():
    import numpy as np
    n = 400
    bench = 100 * 1.0005 ** np.arange(n)
    up = 100 * 1.003 ** np.arange(n)
    gap = up.copy()
    gap[-30] = np.nan                                     # one missing session inside every window
    T = vh.template_table(_panel({"UP": up, "GAP": gap}, bench), ["UP", "GAP"])
    assert int(T["GAP"].iloc[-1]) == int(T["UP"].iloc[-1]) == 8


def test_random_filter_rate():
    idx = pd.bdate_range("2018-01-01", "2025-12-31")
    R = vh.random_filter(idx, ["S%d" % i for i in range(400)], 0.4)
    assert abs(float(R.values.mean()) - 0.4) < 0.02
    q = pd.PeriodIndex(idx, freq="Q")
    assert (R.groupby(q).nunique() == 1).all().all()      # constant within a quarter (no churn)


def test_surveillance_classify():
    import nse_surveillance as ns
    asm = [{"symbol": "AAA", "asmSurvIndicator": "Stage I"}, {"symbol": "BBB", "asmSurvIndicator": "Stage III"}]
    gsm = [{"symbol": "CCC", "gsmStage": "II"}]
    sl = [{"Symbol": "DDD", "Series": "EQ", "Band": "5"}, {"Symbol": "EEE", "Series": "BE", "Band": "20"},
          {"Symbol": "FFF", "Series": "EQ", "Band": "No Band"}, {"Symbol": "AAA", "Series": "EQ", "Band": "20"}]
    out = ns.classify(asm, gsm, sl)
    assert set(out) == {"BBB", "CCC", "DDD", "EEE"}          # Stage I and a normal band stay in
    assert "ASM Stage III" in out["BBB"] and "5% price band" in out["DDD"] and "trade-for-trade" in out["EEE"]


def test_reb2_two_way_reset_with_band():
    import numpy as np
    idx = pd.bdate_range("2024-01-01", periods=5)
    cols = ["A", "B", "C"]
    C = pd.DataFrame(100.0, index=idx, columns=cols)
    atr = pd.DataFrame(2.0, index=idx, columns=cols)        # target = 1e6 * 0.001 / 2 = 500 shares
    g = {"sma100": C * 0 + 50, "gap90": C * 0 > 1, "liq": C * 0 == 0, "atr20": atr,
         "b_up200": pd.Series(True, index=idx)}
    for lb in (60, 90, 120):
        g["clenow%d" % lb] = pd.DataFrame([[3.0, 2.0, 1.0]] * 5, index=idx, columns=cols)
    f = {"has": C * 0 == 0, "atr": atr}
    ctx = {"C": C, "g": g, "f": f, "stocks": cols, "etfs": [], "score": lambda d: (None, {})}
    d = idx[-1]
    pos = {"A": {"sh": 700.0, "entry": 90, "entry_date": idx[0], "last": 100, "kind": "stock"},   # +40 % -> trim
           "B": {"sh": 530.0, "entry": 90, "entry_date": idx[0], "last": 100, "kind": "stock"},   # +6 % -> inside band
           "C": {"sh": 300.0, "entry": 90, "entry_date": idx[0], "last": 100, "kind": "stock"}}   # -40 % -> top up
    fl = dict(vh.NONE, reb2=True, reb_band=0.10)
    vh.H["top_pct"], keep = 1.0, vh.H["top_pct"]
    try:
        r = vh.decide(d, ctx, fl, 1e6, 5e5, pos, 2)              # n_dec 2 = a reset day
        r_off = vh.decide(d, ctx, fl, 1e6, 5e5, pos, 3)          # odd decision = no reset
    finally:
        vh.H["top_pct"] = keep
    assert dict(r["trims"]) == {"A": 200.0}
    assert [s for s, _a in r["adds"]] == ["C"] and abs(dict(r["adds"])["C"] - 200 * 100) < 1e-6
    assert not r_off["trims"] and not r_off["adds"]

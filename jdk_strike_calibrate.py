"""Calibrate JdK formula variants against Strike.Money's published values.

For each (symbol, parameter_set), compute RS-Ratio + RS-Momentum and score
the fit against Strike's reported numbers. Identify which configuration
minimizes the error across the 15 valid samples.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf

# Strike.Money values from user's CSV (2026-05-19 16:01 IST, Nifty 500 weekly)
STRIKE = {
    "SOLARINDS":  (112.26, 104.04),
    "GESHIP":     (119.51,  99.66),
    "NAVINFLUOR": (108.25,  98.27),
    "BSE":        (118.82, 105.54),
    "MCX":        (120.60, 101.67),
    "VIJAYA":     (108.25, 105.79),
    "WOCKPHARMA": (105.06, 103.48),
    "NEULANDLAB": (103.03, 108.89),
    "NAM-INDIA":  (110.60, 103.98),
    "NESTLEIND":  (106.75, 102.46),
    "CAPLIPOINT": (100.56, 104.60),
    "TORNTPHARM": (108.32,  97.70),
    "ENGINERSIN": (113.87, 105.55),
    "SYRMA":      (115.73, 105.61),
    "GLENMARK":   (112.24, 101.33),
}
BENCH = "^CRSLDX"


def jdk(stock_w: pd.Series, bench_w: pd.Series,
        length: int,
        double_pass: bool,
        intermediate_sma: bool,
        final_smooth: int,
        mom_smooth: int) -> tuple[float, float]:
    """Return (RS-Ratio, RS-Momentum) for the last weekly bar."""
    df = pd.merge(stock_w.rename("s"), bench_w.rename("m"),
                  left_index=True, right_index=True, how="inner")
    if len(df) < length * 3:
        return (np.nan, np.nan)
    rs = df["s"] / df["m"].replace(0, np.nan)
    sma1 = rs.rolling(length).mean()
    rs1 = 100.0 + ((rs - sma1) / sma1.replace(0, np.nan)) * 100.0
    if double_pass:
        if intermediate_sma:
            rs2 = rs1.rolling(length).mean()
            sma2 = rs2.rolling(length).mean()
            ratio = 100.0 + ((rs2 - sma2) / sma2.replace(0, np.nan)) * 100.0
        else:
            sma2 = rs1.rolling(length).mean()
            ratio = 100.0 + ((rs1 - sma2) / sma2.replace(0, np.nan)) * 100.0
    else:
        ratio = rs1
    if final_smooth > 1:
        ratio = ratio.rolling(final_smooth).mean()
    roc = 100.0 * (ratio / ratio.shift(1).replace(0, np.nan))
    mom = roc.rolling(mom_smooth).mean() if mom_smooth > 0 else roc
    return float(ratio.iloc[-1]), float(mom.iloc[-1])


def load_weekly(symbol: str, period="5y", auto_adjust=True) -> pd.Series:
    import data_provider as dp
    yf_sym = symbol if symbol.startswith("^") else f"{symbol}.NS"
    df = dp.fetch_ohlcv(yf_sym, period=period, interval="1wk", use_cache=True, auto_adjust=auto_adjust)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].dropna()


def main():
    print("Fetching weekly data for benchmark + 15 symbols (this takes ~30 sec)...")
    # Use 5y history so longer-length variants have enough data
    bench_adj   = load_weekly(BENCH, auto_adjust=True)
    bench_raw   = load_weekly(BENCH, auto_adjust=False)
    print(f"  Bench (adj): {len(bench_adj)} weekly bars, last {bench_adj.index[-1].date()}")
    print(f"  Bench (raw): {len(bench_raw)} weekly bars, last {bench_raw.index[-1].date()}")

    stocks_adj = {sym: load_weekly(sym, auto_adjust=True)  for sym in STRIKE}
    stocks_raw = {sym: load_weekly(sym, auto_adjust=False) for sym in STRIKE}

    # Parameter grid — test many variants of the JdK formula
    variants = []
    for length in (5, 8, 10, 12, 14, 20, 26):
        for double in (True, False):
            for inter in (True, False) if double else (False,):
                for smooth in (1, 3, 5):
                    for mom_smooth in (1, 3, length):
                        variants.append({
                            "length": length, "double": double,
                            "inter": inter, "smooth": smooth,
                            "mom_smooth": mom_smooth,
                        })

    print(f"Testing {len(variants)} parameter variants on {len(STRIKE)} symbols × 2 price modes...")

    rows = []
    for adj_mode in ("adj", "raw"):
        stocks = stocks_adj if adj_mode == "adj" else stocks_raw
        bench  = bench_adj  if adj_mode == "adj" else bench_raw
        for v in variants:
            ratio_errs = []
            mom_errs = []
            quad_matches = 0
            n_valid = 0
            for sym, (strike_r, strike_m) in STRIKE.items():
                if sym not in stocks: continue
                r, m = jdk(stocks[sym], bench,
                            length=v["length"], double_pass=v["double"],
                            intermediate_sma=v["inter"], final_smooth=v["smooth"],
                            mom_smooth=v["mom_smooth"])
                if np.isnan(r) or np.isnan(m): continue
                n_valid += 1
                ratio_errs.append(abs(r - strike_r))
                mom_errs.append(abs(m - strike_m))
                our_q  = ("LEADING" if r >= 100 and m >= 100 else
                          "WEAKENING" if r >= 100 and m < 100 else
                          "LAGGING" if r < 100 and m < 100 else "IMPROVING")
                str_q  = ("LEADING" if strike_r >= 100 and strike_m >= 100 else
                          "WEAKENING" if strike_r >= 100 and strike_m < 100 else
                          "LAGGING" if strike_r < 100 and strike_m < 100 else "IMPROVING")
                if our_q == str_q: quad_matches += 1
            if n_valid == 0: continue
            rows.append({
                "adj": adj_mode,
                "length": v["length"], "double": v["double"], "inter": v["inter"],
                "smooth": v["smooth"], "mom_sm": v["mom_smooth"],
                "n": n_valid,
                "mean_ratio_err": round(np.mean(ratio_errs), 2),
                "mean_mom_err":   round(np.mean(mom_errs), 2),
                "quad_match_pct": round(quad_matches / n_valid * 100, 1),
                "combined_score": round(np.mean(ratio_errs) + np.mean(mom_errs) * 2
                                          - quad_matches / n_valid * 30, 2),
            })

    df = pd.DataFrame(rows)
    df_top = df.sort_values("combined_score").head(20)
    print()
    print("=== TOP 20 BEST-FIT CONFIGURATIONS (lower combined_score = better) ===")
    print(df_top.to_string(index=False))
    print()
    print(f"=== Current bull_screener config ===")
    cur = df[(df["length"]==10) & (df["double"]==True) & (df["inter"]==False)
              & (df["smooth"]==1) & (df["mom_sm"]==10) & (df["adj"]=="adj")]
    print(cur.to_string(index=False))


if __name__ == "__main__":
    main()

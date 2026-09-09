"""JdK RRG calibration probe — GESHIP vs Nifty 500.

Tries multiple length / smoothing combinations of the JdK RS-Ratio /
RS-Momentum formula and prints the current quadrant for each variant.
Goal: find the parameter set that reproduces Strike.Money's reading.
"""
import numpy as np
import pandas as pd
import yfinance as yf

SYMBOL    = "GESHIP.NS"
BENCHMARK = "^CRSLDX"   # Nifty 500


def jdk(stock_w: pd.Series, bench_w: pd.Series,
        length: int, double: bool, final_smooth: int) -> tuple[float, float]:
    """Return (RS_Ratio, RS_Momentum) for the *last* weekly bar.

    double         : if True apply the double-normalization pass (textbook)
    final_smooth   : SMA window applied after the last normalization (0/1 = off)
    """
    df = pd.merge(stock_w.rename("s"), bench_w.rename("m"),
                  left_index=True, right_index=True, how="inner")
    rs = df["s"] / df["m"].replace(0, np.nan)
    sma1 = rs.rolling(length).mean()
    rs1  = 100.0 + ((rs - sma1) / sma1.replace(0, np.nan)) * 100.0
    if double:
        sma2 = rs1.rolling(length).mean()
        ratio = 100.0 + ((rs1 - sma2) / sma2.replace(0, np.nan)) * 100.0
    else:
        ratio = rs1
    if final_smooth and final_smooth > 1:
        ratio = ratio.rolling(final_smooth).mean()
    # Momentum = smoothed ROC of ratio
    roc = 100.0 * (ratio / ratio.shift(1).replace(0, np.nan))
    mom = roc.rolling(length).mean()
    if final_smooth and final_smooth > 1:
        mom = mom.rolling(final_smooth).mean()
    return float(ratio.iloc[-1]), float(mom.iloc[-1])


def quadrant(r, m):
    if any(map(np.isnan, [r, m])): return "n/a"
    if r >= 100 and m >= 100: return "LEADING"
    if r >= 100 and m <  100: return "WEAKENING"
    if r <  100 and m <  100: return "LAGGING"
    return "IMPROVING"


def main():
    print(f"Fetching {SYMBOL} and {BENCHMARK} weekly bars (3 years)...")
    import data_provider as dp
    stock = dp.fetch_ohlcv(SYMBOL,    period="3y", interval="1wk", use_cache=True, auto_adjust=True)
    bench = dp.fetch_ohlcv(BENCHMARK, period="3y", interval="1wk", use_cache=True, auto_adjust=True)
    if isinstance(stock.columns, pd.MultiIndex):
        stock.columns = stock.columns.get_level_values(0)
    if isinstance(bench.columns, pd.MultiIndex):
        bench.columns = bench.columns.get_level_values(0)
    if stock.empty or bench.empty:
        print("ERROR: empty data. Check symbols or network.")
        return
    s = stock["Close"].dropna()
    b = bench["Close"].dropna()
    print(f"  stock  bars: {len(s)}, last date: {s.index[-1].date()}, last close: {s.iloc[-1]:.2f}")
    print(f"  bench  bars: {len(b)}, last date: {b.index[-1].date()}, last close: {b.iloc[-1]:.2f}")
    print()

    grid = []
    for length in (5, 8, 10, 12, 14, 20):
        for double in (True, False):
            for smooth in (1, 3, 5):
                r, m = jdk(s, b, length, double, smooth)
                grid.append({
                    "length":  length,
                    "double":  "Y" if double else "N",
                    "smooth":  smooth,
                    "RS_Ratio": round(r, 2),
                    "RS_Mom":   round(m, 2),
                    "Quadrant": quadrant(r, m),
                })
    df = pd.DataFrame(grid)
    print("All variants (sorted by RS_Mom, ascending):")
    print(df.sort_values("RS_Mom").to_string(index=False))
    print()
    print("Quadrant counts:")
    print(df["Quadrant"].value_counts())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import glob
import pandas as pd
import logging
from weinstein_xray_screener import get_xray_scorecard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = "FINAL_XRay_Picks.csv"


def _load_symbols_from_watchlists() -> list:
    """Load all symbols from FINAL_WATCHLIST.csv (Golden Matcher)."""
    symbols = set()
    golden_matcher_file = os.path.join(SCRIPT_DIR, "FINAL_WATCHLIST.csv")

    if os.path.exists(golden_matcher_file):
        try:
            df = pd.read_csv(golden_matcher_file)
            if "Symbol" in df.columns:
                for sym in df["Symbol"].dropna():
                    sym = str(sym).strip().replace("NSE:", "").replace("BSE:", "")
                    if sym:
                        symbols.add(sym)
                logging.info(f"Using {len(symbols)} symbols from {golden_matcher_file}")
            else:
                logging.error(f"'Symbol' column not found in {golden_matcher_file}")
        except Exception as e:
            logging.error(f"Error reading {golden_matcher_file}: {e}")
    else:
        logging.error(f"Golden Matcher file not found: {golden_matcher_file}")

    if not symbols:
        symbols = {"RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"}

    return sorted(symbols)


def _to_yf(sym: str) -> str:
    """Ensure symbol has .NS suffix for yfinance."""
    s = sym.strip().upper().replace("NSE:", "").replace("BSE:", "")
    if not s.endswith(".NS") and not s.endswith(".BO"):
        s += ".NS"
    return s


def run_xray_screener(progress_callback=None, symbols=None,
                      out_file: str = OUTPUT_FILE) -> pd.DataFrame:
    """Run the X-Ray screener and return results as a DataFrame.

    Parameters
    ----------
    progress_callback : callable(idx, total, sym), optional
        Called after each symbol is processed.
    symbols : list[str], optional
        Pre-loaded symbol list (plain NSE codes, no exchange prefix needed).
        When *None* the function reads from Generated_Watchlists or
        xray_custom_symbols.txt (existing behaviour).
    out_file : str, optional
        CSV filename to save results (relative to SCRIPT_DIR).
    """
    if symbols is None:
        raw_symbols = _load_symbols_from_watchlists()
    else:
        raw_symbols = [
            s.strip().upper().replace("NSE:", "").replace("BSE:", "")
            for s in symbols if s and str(s).strip()
        ]
        raw_symbols = sorted(set(raw_symbols))

    yf_symbols = [_to_yf(s) for s in raw_symbols]
    logging.info(f"X-Ray: screening {len(yf_symbols)} symbols")

    results = []
    total = len(yf_symbols)
    for i, sym in enumerate(yf_symbols, 1):
        if progress_callback:
            progress_callback(i, total, sym)
        logging.info(f"[{i}/{total}] Scanning {sym}...")
        try:
            sc = get_xray_scorecard(sym)
            if sc and "error" not in sc:
                m_details = sc.get("Minervini_Details", {})
                p_details = sc.get("Piotroski_Details", {})
                results.append({
                    "Symbol":          sym,
                    "Overall_Rating":  sc.get("Overall_Rating", 0),
                    "Overall_Grade":   sc.get("Overall_Grade", "N/A"),
                    "Minervini_Score": sc.get("Minervini_Score", 0),
                    "Piotroski_Score": sc.get("Piotroski_Score", 0),
                    "ROE":   sc.get("Raw_Metrics", {}).get("ROE", "N/A"),
                    "P/E":   sc.get("Raw_Metrics", {}).get("P/E Ratio", "N/A"),
                    "D/E":   sc.get("Raw_Metrics", {}).get("D/E Ratio", "N/A"),
                    "M: Rev YoY > 20%": m_details.get("Rev YoY > 20%", 0),
                    "M: NI YoY > 25%": m_details.get("NI YoY > 25%", 0),
                    "M: Accel EPS": m_details.get("Accel EPS", 0),
                    "M: ROE > 15%": m_details.get("ROE > 15%", 0),
                    "M: Gross Margin > 15%": m_details.get("Gross Margin > 15%", 0),
                    "M: D/E < 1.5": m_details.get("D/E < 1.5", 0),
                    "M: Current Ratio > 1.0": m_details.get("Current Ratio > 1.0", 0),
                    "M: FCF Positive": m_details.get("FCF Positive", 0),
                    "P: F1 ROA Positive": p_details.get("F1 ROA Positive", 0),
                    "P: F2 OCF Positive": p_details.get("F2 OCF Positive", 0),
                    "P: F3 ROA Improving": p_details.get("F3 ROA Improving", 0),
                    "P: F4 Accrual Ratio < 0": p_details.get("F4 Accrual Ratio < 0", 0),
                    "P: F5 Leverage Decreasing": p_details.get("F5 Leverage Decreasing", 0),
                    "P: F6 Liquidity Improving": p_details.get("F6 Liquidity Improving", 0),
                    "P: F7 No Dilution": p_details.get("F7 No Dilution", 0),
                    "P: F8 Gross Margin Increasing": p_details.get("F8 Gross Margin Increasing", 0),
                    "P: F9 Asset Turnover Increasing": p_details.get("F9 Asset Turnover Increasing", 0)
                })
        except Exception as e:
            logging.error(f"Failed to scan {sym}: {e}")

    if results:
        df = pd.DataFrame(results).sort_values("Overall_Rating", ascending=False)
        df.to_csv(os.path.join(SCRIPT_DIR, out_file), index=False)
        logging.info(f"Saved {len(df)} results to {out_file}")
        return df

    # 10 May 2026 fix: write a header-only CSV on zero results so the file
    # timestamp updates. Without this, a successful run that found no valid
    # candidates looked identical to "never ran" — the freshness check stayed
    # stuck on the previous run's date.
    logging.warning("No valid X-Ray results generated.")
    _empty_cols = [
        "Symbol", "Overall_Rating", "Overall_Grade", "Minervini_Score", "Piotroski_Score",
        "ROE", "P/E", "D/E",
        "M: Rev YoY > 20%", "M: NI YoY > 25%", "M: Accel EPS", "M: ROE > 15%", "M: Gross Margin > 15%",
        "M: D/E < 1.5", "M: Current Ratio > 1.0", "M: FCF Positive",
        "P: F1 ROA Positive", "P: F2 OCF Positive", "P: F3 ROA Improving", "P: F4 Accrual Ratio < 0",
        "P: F5 Leverage Decreasing", "P: F6 Liquidity Improving", "P: F7 No Dilution",
        "P: F8 Gross Margin Increasing", "P: F9 Asset Turnover Increasing"
    ]
    try:
        pd.DataFrame(columns=_empty_cols).to_csv(
            os.path.join(SCRIPT_DIR, out_file), index=False
        )
    except Exception:
        pass
    return pd.DataFrame(columns=_empty_cols)


def main():
    run_xray_screener()


if __name__ == "__main__":
    main()

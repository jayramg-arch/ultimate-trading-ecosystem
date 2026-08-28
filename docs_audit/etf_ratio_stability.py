"""Can a level found on the INDEX be translated to an ETF price?

Index-first only works if the ETF/index ratio is near-constant — otherwise a stop or
target computed on the index maps to the wrong ETF price. "Tracking" is supposed to
mean exactly that, but it needs measuring, and it turns out to be true for one half of
the universe and false for the other.

  JUNIORBEES / ^NSMIDCP          0.85% drift over 90d, 0.16% daily sd
  BANKBEES   / ^NSEBANK          0.74%                 0.18%
  ITBEES     / ^CNXIT            1.48%                 0.22%
  MID150BEES / Midcap150         0.50%                 0.16%
  GOLDBEES   / GC=F              7.59%                 1.42%
  SILVERBEES / SI=F              7.53%                 2.50%

Domestic equity ETFs track tightly enough that a translated level carries under ~1.5%
of error. Gold and silver do NOT, and the reason is not tracking quality: GC=F is USD
gold FUTURES and GOLDBEES is INR spot gold, so the ratio carries the dollar rate and
the futures basis on top of the metal. The same applies to the Nasdaq pair.

CONSEQUENCE — index-first is scoped to DOMESTIC EQUITY-INDEX ETFs. Commodity and
international wrappers keep reading their own price, because their "benchmark" is a
different instrument in a different currency, not the thing they hold.
"""
import os, sys, warnings
import pandas as pd
warnings.filterwarnings("ignore"); sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data_provider as dp, etf_universe as eu

# A foreign futures/index benchmark cannot be translated into an INR wrapper price.
FOREIGN = ("GC=F", "SI=F", "^NDX", "^GSPC", "^IXIC")

def ratio(etf, bm, days=90):
    a = dp.fetch_ohlcv(etf, period="1y", interval="1d")
    b = dp.fetch_ohlcv(bm, period="1y", interval="1d")
    if a is None or b is None: return None
    a, b = a.rename(columns=str.title), b.rename(columns=str.title)
    # Some benchmark frames come back without a Close (empty or index-only response).
    # Guard rather than raise: one missing benchmark must not end the sweep.
    if "Close" not in a.columns or "Close" not in b.columns:
        return None
    j = pd.concat([a["Close"], b["Close"]], axis=1, join="inner").dropna()
    if len(j) < 60: return None
    r = (j.iloc[:, 0] / j.iloc[:, 1]).tail(days)
    return (r.iloc[-1] / r.iloc[0] - 1) * 100, r.pct_change().std() * 100

if __name__ == "__main__":
    print(f"{'ETF':14}{'benchmark':26}{'drift 90d':>11}{'daily sd':>10}   verdict")
    for s, m in eu.ETF_UNIVERSE.items():
        bm = m.get("benchmark_yf")
        if not bm: continue
        out = ratio(s, bm)
        if not out: continue
        d, sd = out
        foreign = bm in FOREIGN
        ok = (abs(d) < 3.0 and sd < 0.5) and not foreign
        why = "translatable" if ok else ("foreign unit" if foreign else "drifts too far")
        print(f"{s:14}{bm:26}{d:>10.2f}%{sd:>9.2f}%   {why}")

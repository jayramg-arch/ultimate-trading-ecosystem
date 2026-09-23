"""NSE delivery history — the cash analogue of open interest.

    python cash_bhavcopy.py                    yesterday and today
    python cash_bhavcopy.py --backfill 120     the last 120 calendar days, skipping holidays
    python cash_bhavcopy.py --from 2024-07-01 --prune     a long backfill, dropping raw files
    python cash_bhavcopy.py --report RELIANCE  what is stored for one name

WHY IT EXISTS (23-Sep-2026). docs/PREREG_cash_levels.md needs one input that is not
already on the S4 panel: delivery percentage. It is the closest true analogue of OI in a
cash market, because it is the only field that says volume was TAKEN rather than churned
— a price move on collapsing delivery is intraday rotation, which is roughly what falling
ATM open interest tells you on an F&O name.

It is also the only H5 input, and H5 cannot run without a history that reaches the trade
window. `sec_bhavdata_full` carries DELIV_QTY and DELIV_PER for every symbol for one day,
and the archive goes back years — the same shape, and the same approach, as fno_bhavcopy.py
used to reconstruct the options book.

STORED AS PARQUET, not CSV. ~2,000 deliverable-series rows a day over a 20-month backfill
is ~900k rows; as CSV that is a ~60 MB file rewritten on every daily run. The OHLCV cache
already uses parquet here for the same reason.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cash_bhav")
OUT = os.path.join(HERE, "data", "delivery_history.parquet")
URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_%s.csv"

# EQ and BE only. The rest (SM, ST, GB…) are SME, trade-to-trade oddities and government
# bonds — never in this universe, and they would triple the row count.
SERIES_KEEP = ("EQ", "BE")
COLS = ["date", "symbol", "series", "close", "ttl_qty", "deliv_qty", "deliv_pct"]

# H5's baseline, pre-registered. Not tunable here.
DELIV_BASELINE_DAYS = 20


def _session():
    import nse_options as no          # the cookie dance already lives there
    return no._get_session()


def raw(day: dt.date, sess=None) -> pd.DataFrame | None:
    """The day's delivery bhavcopy, from the local cache or NSE. None on a holiday."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, day.strftime("%Y%m%d") + ".csv")
    if not os.path.exists(path):
        s = sess or _session()
        r = s.get(URL % day.strftime("%d%m%Y"), timeout=30,
                  headers={"Referer": "https://www.nseindia.com/"})
        # A holiday returns an HTML error page, not a 404 — check the payload, not the code.
        if not r.ok or not r.content[:6].upper().startswith(b"SYMBOL"):
            return None
        with open(path, "wb") as f:
            f.write(r.content)
    try:
        return pd.read_csv(path)
    except Exception:
        os.remove(path)               # a truncated download must not poison the cache
        return None


def derive(df: pd.DataFrame, day: dt.date) -> pd.DataFrame:
    """One tidy row per deliverable-series symbol.

    Every column name in this file is prefixed with a SPACE (' SERIES', ' DELIV_PER') —
    NSE has shipped it that way for years. Stripping them is not cosmetic: reading
    df['DELIV_PER'] raises KeyError, and a bare except around it would have turned the
    whole feed into a silent empty.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=COLS)
    d = df.rename(columns={c: str(c).strip() for c in df.columns})
    if "SERIES" not in d.columns or "DELIV_PER" not in d.columns:
        return pd.DataFrame(columns=COLS)
    d["SERIES"] = d["SERIES"].astype(str).str.strip()
    d = d[d["SERIES"].isin(SERIES_KEEP)].copy()

    # DELIV_QTY / DELIV_PER are literally "-" on rows where the exchange did not compute
    # them. Coerced to NaN and left NaN: the pre-registration says missing is EXCLUDED,
    # never zero, and a zero here would read as "nothing was delivered".
    out = pd.DataFrame({
        "date": day.strftime("%Y-%m-%d"),
        "symbol": d["SYMBOL"].astype(str).str.strip(),
        "series": d["SERIES"],
        "close": pd.to_numeric(d.get("CLOSE_PRICE"), errors="coerce"),
        "ttl_qty": pd.to_numeric(d.get("TTL_TRD_QNTY"), errors="coerce"),
        "deliv_qty": pd.to_numeric(d.get("DELIV_QTY"), errors="coerce"),
        "deliv_pct": pd.to_numeric(d.get("DELIV_PER"), errors="coerce"),
    })
    return out[COLS]


def load() -> pd.DataFrame:
    if not os.path.exists(OUT):
        return pd.DataFrame(columns=COLS)
    try:
        return pd.read_parquet(OUT)
    except Exception:
        return pd.DataFrame(columns=COLS)


def store(new: pd.DataFrame) -> int:
    if new is None or new.empty:
        return 0
    old = load()
    # Concatenating onto an all-NA empty frame is deprecated and warns on every first run.
    both = new[COLS].copy() if old.empty else pd.concat([old, new], ignore_index=True)[COLS]
    both = both.drop_duplicates(subset=["date", "symbol"], keep="last")
    both = both.sort_values(["date", "symbol"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    both.to_parquet(tmp, index=False)     # tmp + replace: a killed run must not truncate
    os.replace(tmp, OUT)
    return len(both) - len(old)


def fetch_day(day: dt.date, sess=None, have: set | None = None, prune: bool = False):
    """The day's rows, WITHOUT storing. None = already have it; empty = holiday.

    Storing per day would rewrite the whole parquet 440 times on a 20-month backfill —
    quadratic, and by the end each write is a million rows. main() batches instead.
    """
    if have is not None and day.strftime("%Y-%m-%d") in have:
        return None
    df = raw(day, sess)
    if df is None:
        return pd.DataFrame(columns=COLS)
    out = derive(df, day)
    if prune and not out.empty:
        try:
            os.remove(os.path.join(CACHE, day.strftime("%Y%m%d") + ".csv"))
        except OSError:
            pass
    return out


def run_day(day: dt.date, sess=None, have: set | None = None, prune: bool = False) -> int:
    """Fetch and store one day. Kept for callers that want a single day done end to end."""
    out = fetch_day(day, sess, have, prune)
    if out is None:
        return -1
    return store(out) if not out.empty else 0


def delivery_signal(symbol: str, as_of: str | None = None) -> dict:
    """H5's input: the day's delivery % against its own trailing mean.

    Shared by the live LEVEL CHECK and the pre-registered test, for the same reason
    volume_profile is — the rule measured must be the rule that ships. Returns {} when the
    history does not cover the name or the date; never a fabricated zero.
    """
    d = load()
    if d.empty:
        return {}
    d = d[d["symbol"].astype(str).str.upper() == str(symbol).upper().replace(".NS", "")]
    if as_of:
        d = d[d["date"] <= str(as_of)]
    d = d.dropna(subset=["deliv_pct"]).sort_values("date")
    if len(d) < DELIV_BASELINE_DAYS + 1:
        return {}
    win = d.iloc[-(DELIV_BASELINE_DAYS + 1):]
    # THE WINDOW MUST BE CONTIGUOUS. Taking the last 21 rows says nothing about whether
    # they are consecutive sessions: mid-backfill, ANANDRATHI's "20-day mean" was drawn
    # from rows spanning Aug-2025 to Sep-2026 and still looked like a clean 38.8%. A
    # baseline that quietly straddles a hole is worse than no baseline, so a window wider
    # than ~45 calendar days for 21 sessions is treated as missing.
    span = (pd.to_datetime(win["date"].iloc[-1]) - pd.to_datetime(win["date"].iloc[0])).days
    if span > 45:
        return {}
    cur = float(win["deliv_pct"].iloc[-1])
    base = float(win["deliv_pct"].iloc[:-1].mean())
    if not base:
        return {}
    return {"deliv_pct": cur, "mean20": base, "ratio": cur / base,
            "date": str(win["date"].iloc[-1]), "span_days": span}


def report(sym: str, n: int = 20) -> str:
    d = load()
    d = d[d["symbol"].astype(str).str.upper() == sym.upper()].sort_values("date").tail(n)
    if d.empty:
        return "no rows for %s" % sym
    return d.to_string(index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", type=int, default=0, help="calendar days back to fetch")
    ap.add_argument("--from", dest="frm", help="backfill FROM this date forward, YYYY-MM-DD")
    ap.add_argument("--prune", action="store_true",
                    help="delete each day's raw CSV once its rows are stored")
    ap.add_argument("--batch", type=int, default=25,
                    help="store every N days rather than every day (backfill speed)")
    ap.add_argument("--report", help="print the last rows for one symbol and exit")
    a = ap.parse_args()

    if a.report:
        print(report(a.report))
        return 0

    today = dt.date.today()
    if a.frm:
        start = dt.date.fromisoformat(a.frm)
        days = [start + dt.timedelta(days=i) for i in range((today - start).days + 1)]
    elif a.backfill:
        days = [today - dt.timedelta(days=i) for i in range(a.backfill, -1, -1)]
    else:
        days = [today - dt.timedelta(days=1), today]

    days = [d for d in days if d.weekday() < 5]      # NSE is shut at the weekend
    have = set(load()["date"].astype(str)) if os.path.exists(OUT) else set()
    sess, added, fetched, skipped, holidays = _session(), 0, 0, 0, 0
    batch: list = []

    def flush():
        nonlocal batch, added
        if batch:
            added += store(pd.concat(batch, ignore_index=True))
            batch = []

    for d in days:
        out = fetch_day(d, sess, have, prune=a.prune)
        if out is None:
            skipped += 1
        elif out.empty:
            holidays += 1
        else:
            batch.append(out)
            fetched += 1
            print("  %s  %d rows" % (d, len(out)), flush=True)
            if len(batch) >= a.batch:
                flush()
                print("    … stored (%d days so far)" % fetched, flush=True)
    flush()

    tot = load()
    print("\n%d day(s) fetched, %d already had, %d holiday/absent · +%d rows"
          % (fetched, skipped, holidays, added))
    if not tot.empty:
        print("history: %d rows · %d symbols · %s → %s -> %s"
              % (len(tot), tot["symbol"].nunique(), tot["date"].min(), tot["date"].max(),
                 os.path.relpath(OUT, HERE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

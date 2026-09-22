"""fno_bhavcopy.py — daily F&O derivatives history from the NSE bhavcopy.

21-Sep-2026 (P0 of the derivatives plan). `oi_snapshot.py` records the LIVE option
chain, one row per name per day, and it had exactly one day in it: the live chain
cannot be read for a past date, so on that path every options rule stays unvalidated
for months. The NSE F&O bhavcopy solves that — ONE file per trading day carries EVERY
contract (629 stock futures + 29,824 stock options on 18-Sep), the archive goes back
years, and everything S4's Futures-OI and Options-OI rows print can be recomputed from
it. Verified against the live chain: UNOMINDA 18-Sep reconstructs max pain 1240.0,
call wall 1300, put wall 1200, PCR 0.73 — the same numbers the panel showed.

WHAT IT STORES  (data/fno_history.csv, one row per symbol per day)
    fut_oi, fut_doi, fut_settle, fut_close, underlying   near-month stock future
    fut_oi_next                                          next month, for rollover
    pcr, max_pain, call_wall, put_wall, ce_oi, pe_oi     near-expiry option chain
    atm_strike, atm_ce_doi, atm_pe_doi                   writers adding at the money
    expiry, days_to_expiry                               the walls' shelf life
The FUTURES BASIS (S4's `basis L` / `basis S`) is NOT stored: it is an event-weighted
mean over the last N daily prints of ΔOI and price, so it is derived from this history
downstream rather than frozen here at one window length.

MISSING IS NEVER ZERO — every field is None when the contract or the field is absent;
a max pain of 0 would draw a confident line under every stop.

    python fno_bhavcopy.py                    today (or the last trading day)
    python fno_bhavcopy.py --backfill 120     the last 120 calendar days, skipping holidays
    python fno_bhavcopy.py --date 2026-09-18  one day
    python fno_bhavcopy.py --report UNOMINDA  what the walls did, last 20 rows

Raw zips are cached under data/fno_bhav/ so a re-run costs no download. A missing day
(holiday, or a file NSE has not published yet) is a skip, never an error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import sys
import zipfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "fno_bhav")
OUT = os.path.join(HERE, "data", "fno_history.csv")
URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_%s_F_0000.csv.zip"

COLS = ["date", "symbol", "expiry", "days_to_expiry", "underlying",
        "fut_oi", "fut_doi", "fut_settle", "fut_close", "fut_oi_next",
        "pcr", "max_pain", "call_wall", "put_wall", "ce_oi", "pe_oi",
        "atm_strike", "atm_ce_doi", "atm_pe_doi"]


def _session():
    import nse_options as no          # the cookie dance already lives there
    return no._get_session()


def raw(day: dt.date, sess=None) -> pd.DataFrame | None:
    """The day's bhavcopy as a frame, from the local cache or NSE. None if absent."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, day.strftime("%Y%m%d") + ".zip")
    if not os.path.exists(path):
        s = sess or _session()
        r = s.get(URL % day.strftime("%Y%m%d"), timeout=30,
                  headers={"Referer": "https://www.nseindia.com/"})
        if not r.ok or r.content[:2] != b"PK":
            return None                      # holiday / not published yet
        with open(path, "wb") as f:
            f.write(r.content)
    try:
        with zipfile.ZipFile(path) as z:
            return pd.read_csv(z.open(z.namelist()[0]))
    except Exception:
        os.remove(path)                      # a truncated download must not poison the cache
        return None


def _num(x):
    try:
        v = float(x)
        return None if pd.isna(v) else v
    except Exception:
        return None


def derive(df: pd.DataFrame, day: dt.date) -> pd.DataFrame:
    """Per-symbol derivatives row for one trading day — stock F&O only (STF/STO).
    Index futures/options (IDF/IDO) are skipped: this feeds single-name trade levels."""
    fut = df[df["FinInstrmTp"] == "STF"].copy()
    opt = df[df["FinInstrmTp"] == "STO"].copy()
    if fut.empty and opt.empty:
        return pd.DataFrame(columns=COLS)
    for f in (fut, opt):
        f["XpryDt"] = pd.to_datetime(f["XpryDt"], errors="coerce")
    rows = []
    for sym, of in opt.groupby("TckrSymb"):
        exps = sorted(x for x in of["XpryDt"].dropna().unique())
        if not exps:
            continue
        near = pd.Timestamp(exps[0])
        o = of[of["XpryDt"] == near]
        ce, pe = o[o["OptnTp"] == "CE"], o[o["OptnTp"] == "PE"]
        ff = fut[fut["TckrSymb"] == sym]
        fn = ff[ff["XpryDt"] == near]
        fnx = ff[ff["XpryDt"] > near].sort_values("XpryDt").head(1)
        spot = _num(o["UndrlygPric"].iloc[0]) if len(o) else None
        ce_oi, pe_oi = float(ce["OpnIntrst"].sum()), float(pe["OpnIntrst"].sum())

        # walls: the fattest CE at/above spot and PE at/below it — the strikes writers defend
        cw = pw = None
        if spot:
            up = ce[(ce["StrkPric"] >= spot) & ce["OpnIntrst"].notna()]
            dn = pe[(pe["StrkPric"] <= spot) & pe["OpnIntrst"].notna()]
            if len(up):
                cw = _num(up.loc[up["OpnIntrst"].idxmax(), "StrkPric"])
            if len(dn):
                pw = _num(dn.loc[dn["OpnIntrst"].idxmax(), "StrkPric"])

        # max pain: the strike where the writers' total payout is smallest
        mp = None
        ks = sorted({float(k) for k in o["StrkPric"].dropna()})
        if ks and (ce_oi or pe_oi):
            def pain(k: float) -> float:
                a = ce[ce["StrkPric"] < k]
                b = pe[pe["StrkPric"] > k]
                return float(((k - a["StrkPric"]) * a["OpnIntrst"]).sum()
                             + ((b["StrkPric"] - k) * b["OpnIntrst"]).sum())
            mp = min(ks, key=pain)

        # at the money: are writers ADDING where price actually is?
        atm = atm_c = atm_p = None
        if spot and ks:
            atm = min(ks, key=lambda k: abs(k - spot))
            c = ce[ce["StrkPric"] == atm]
            p = pe[pe["StrkPric"] == atm]
            atm_c = _num(c["ChngInOpnIntrst"].sum()) if len(c) else None
            atm_p = _num(p["ChngInOpnIntrst"].sum()) if len(p) else None

        rows.append({
            "date": day.strftime("%Y-%m-%d"), "symbol": str(sym),
            "expiry": near.strftime("%Y-%m-%d"),
            "days_to_expiry": (near.date() - day).days,
            "underlying": spot,
            "fut_oi": _num(fn["OpnIntrst"].iloc[0]) if len(fn) else None,
            "fut_doi": _num(fn["ChngInOpnIntrst"].iloc[0]) if len(fn) else None,
            "fut_settle": _num(fn["SttlmPric"].iloc[0]) if len(fn) else None,
            "fut_close": _num(fn["ClsPric"].iloc[0]) if len(fn) else None,
            "fut_oi_next": _num(fnx["OpnIntrst"].iloc[0]) if len(fnx) else None,
            "pcr": round(pe_oi / ce_oi, 3) if ce_oi else None,
            "max_pain": mp, "call_wall": cw, "put_wall": pw,
            "ce_oi": ce_oi or None, "pe_oi": pe_oi or None,
            "atm_strike": atm, "atm_ce_doi": atm_c, "atm_pe_doi": atm_p,
        })
    return pd.DataFrame(rows, columns=COLS)


def load() -> pd.DataFrame:
    if not os.path.exists(OUT):
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(OUT)


def store(new: pd.DataFrame) -> int:
    if new is None or new.empty:
        return 0
    old = load()
    both = pd.concat([old, new], ignore_index=True)[COLS]
    both = both.drop_duplicates(subset=["date", "symbol"], keep="last")
    both = both.sort_values(["date", "symbol"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(OUT, both.to_csv(index=False))
    except Exception:
        both.to_csv(OUT, index=False)
    return len(both) - len(old)


def run_day(day: dt.date, sess=None, have: set | None = None, prune: bool = False) -> int:
    """prune=True deletes the raw zip once the day's rows are stored. A 20-month backfill
    is ~1.1 MB x 440 days of zips for data that has already been reduced to 19 columns;
    the derived history is what anything downstream reads."""
    if have is not None and day.strftime("%Y-%m-%d") in have:
        return -1                                   # already stored
    df = raw(day, sess)
    if df is None:
        return 0
    n = store(derive(df, day))
    if prune and n:
        try:
            os.remove(os.path.join(CACHE, day.strftime("%Y%m%d") + ".zip"))
        except OSError:
            pass
    return n


def report(sym: str, n: int = 20) -> str:
    d = load()
    d = d[d["symbol"].str.upper() == sym.upper()].tail(n)
    if d.empty:
        return f"no rows for {sym}"
    keep = ["date", "underlying", "fut_oi", "fut_doi", "pcr", "max_pain",
            "call_wall", "put_wall", "days_to_expiry"]
    return d[keep].to_string(index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", type=int, default=0, help="calendar days back to fetch")
    ap.add_argument("--from", dest="frm", help="backfill FROM this date forward, YYYY-MM-DD")
    ap.add_argument("--date", help="one day, YYYY-MM-DD")
    ap.add_argument("--report", help="print the last rows for a symbol")
    ap.add_argument("--prune", action="store_true",
                    help="delete each raw zip after its rows are stored (long backfills)")
    a = ap.parse_args()
    os.chdir(HERE)

    if a.report:
        print(report(a.report)); return 0

    have = set(load()["date"].astype(str)) if os.path.exists(OUT) else set()
    sess = _session()
    if a.date:
        days = [dt.date.fromisoformat(a.date)]
    elif a.frm:
        d0, d1 = dt.date.fromisoformat(a.frm), dt.date.today()
        days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
        days = [d for d in days if d.weekday() < 5]
    elif a.backfill:
        today = dt.date.today()
        days = [today - dt.timedelta(days=i) for i in range(a.backfill + 1)]
        days = [d for d in days if d.weekday() < 5]      # NSE trades Mon-Fri
        days.sort()
    else:
        days = [dt.date.today()]
        if days[0].weekday() >= 5:                        # weekend: take Friday
            days = [days[0] - dt.timedelta(days=days[0].weekday() - 4)]

    added = skipped = nofile = 0
    for d in days:
        n = run_day(d, sess, have, a.prune)
        if n < 0:
            skipped += 1
        elif n == 0:
            nofile += 1
        else:
            added += n
            print(f"  {d}  +{n} rows")
    tot = load()
    print(f"days: {len(days)} · added {added} rows · already had {skipped} · no file (holiday or not yet published) {nofile}")
    if len(tot):
        print(f"store: {len(tot)} rows · {tot['symbol'].nunique()} symbols · "
              f"{tot['date'].min()} → {tot['date'].max()} -> {os.path.relpath(OUT, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

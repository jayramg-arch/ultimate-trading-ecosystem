# -*- coding: utf-8 -*-
"""room_obstacle_audit.py — does the FIRST overhead obstacle actually stop the trade?

Pre-registration: docs/PREREG_room_obstacle_class.md (H10). READ-ONLY: no gate, no Pine.

For every filled GO trade in an s4go run, rebuild the board's own Room read at the entry
date (data pinned to that date, zone_engine.overhead_room on D + W frames), grade the first
obstacle HARD / SOFT / CLEAR, and ask whether price went through it.

Usage:
    python room_obstacle_audit.py [--run 20260909_055448] [--limit N] [--boot 2000]
Writes validation_runs/_room_obstacle_<run>.csv (per trade) and prints the tables.
"""
from __future__ import annotations
import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import data_provider as dp        # noqa: E402
import zone_engine as ze          # noqa: E402

HARD_PREFIX = ("SZ", "S/R·W", "S/R·M", "PivR·W", "PivR·M")
SOFT_PREFIX = ("S/R·D", "PivR·D", "Pv", "lastPH")


def classify(src) -> str:
    if not src:
        return "CLEAR"
    s = str(src)
    if s.startswith(HARD_PREFIX):
        return "HARD"
    if s.startswith(SOFT_PREFIX):
        return "SOFT"
    return "OTHER"


def bucket(r):
    if r is None or (isinstance(r, float) and np.isnan(r)):
        return "clear"
    return "<1R" if r < 1 else ("1-2R" if r < 2 else ">=2R")


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    w = df.resample("W-MON", closed="left", label="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    return w.iloc[:-1] if len(w) > 1 else w        # drop the forming week (confirmed weeks only)


def family(sym_row) -> str:
    t = str(sym_row.get("GO_Triggers", "")) + " " + str(sym_row.get("Mode", ""))
    fd = sym_row.get("forward_days_used")
    try:
        fd = float(fd)
    except Exception:
        fd = np.nan
    if fd >= 100:
        return "POS"
    if fd > 0:
        return "SWG"
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="20260909_055448")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()

    det = pd.read_csv(os.path.join(HERE, "validation_runs", f"validation_{a.run}_details.csv"))
    det = det[det["Entry_Price"].notna() & det["SL_price"].notna()].copy()
    if a.limit:
        det = det.head(a.limit)
    print(f"run {a.run}: {len(det)} filled GO trades")

    rows = []
    for i, r in det.iterrows():
        sym, ed = r["Symbol"], str(r["Entry_Date"])[:10]
        entry, sl, t1 = float(r["Entry_Price"]), float(r["SL_price"]), float(r["T1_price"])
        risk = entry - sl
        rec = dict(Symbol=sym, Entry_Date=ed, family=family(r), entry=entry, risk=risk,
                   hit_t1=bool(r["Hit_T1"]), ret_pct=float(r["Return_pct"]),
                   runup_pct=float(r["Max_Runup_pct"]), exit=r["Exit_Reason"],
                   alpha=float(r["Alpha_Matched_pct"]))
        rec["R"] = rec["ret_pct"] / 100 * entry / risk if risk > 0 else np.nan
        rec["runup_R"] = rec["runup_pct"] / 100 * entry / risk if risk > 0 else np.nan
        try:
            d = dp.fetch_ohlcv(sym, period="3y", interval="1d", pinned_date=ed)
            if d is None or len(d) < 120:
                rec.update(src=None, cls="NODATA"); rows.append(rec); continue
            d = d[d.index <= pd.Timestamp(ed)]
            frames = {"D": d, "W": weekly(d)}
            room = ze.overhead_room(frames, price=entry, entry=entry, risk=risk)
            src, obs = room.get("source"), room.get("obstacle")
            rec.update(src=src, obstacle=obs, room_r=room.get("room_r"),
                       clear=room.get("clear"), in_supply=room.get("in_supply"),
                       obstacle_real=room.get("obstacle_real"), src_real=room.get("source_real"))
            if obs is not None and risk > 0:
                rec["room_r"] = (obs - entry) / risk
                rec["dist_pct"] = (obs - entry) / entry * 100
                rec["broke"] = rec["runup_pct"] >= rec["dist_pct"]
            rec["cls"] = classify(src)
            # the first HARD obstacle, even when a soft one sits closer
            hard = [s for s in room.get("sources", []) if classify(s.split(" ", 1)[1]) == "HARD"]
            if hard:
                hp = float(hard[0].split(" ", 1)[0])
                rec["hard_room_r"] = (hp - entry) / risk
            # age / touches of a Daily S/R first obstacle
            if src and str(src).startswith("S/R·D"):
                for L in ze.detect_sr_levels(d, "D"):
                    if abs(float(L["price"]) - obs) < 1e-6:
                        rec["touches"] = L.get("touches"); rec["age_band"] = L.get("age_band")
                        break
        except Exception as e:
            rec.update(src=None, cls="ERR", err=str(e)[:80])
        rows.append(rec)
        if (len(rows) % 25) == 0:
            print(f"  {len(rows)}/{len(det)}", flush=True)

    df = pd.DataFrame(rows)
    for c in ("broke", "hit_t1"):
        df[c] = pd.to_numeric(df[c].map({True: 1.0, False: 0.0}), errors="coerce")
    out = os.path.join(HERE, "validation_runs", f"_room_obstacle_{a.run}.csv")
    df.to_csv(out, index=False)
    df["bucket"] = df["room_r"].apply(bucket)
    df.loc[df["cls"] == "CLEAR", "bucket"] = "clear"

    pd.set_option("display.width", 200)
    print("\nclass of FIRST obstacle:")
    print(df["cls"].value_counts().to_string())
    print("\nfirst-obstacle source (top 10):")
    print(df["src"].value_counts().head(10).to_string())

    def table(sub, title):
        g = sub.groupby(["cls", "bucket"]).agg(
            n=("R", "size"), hit_t1=("hit_t1", "mean"), mean_R=("R", "mean"), med_R=("R", "median"),
            broke=("broke", "mean"), runup_R=("runup_R", "median")).reset_index()
        g["hit_t1"] = (g["hit_t1"] * 100).round(1); g["broke"] = (g["broke"] * 100).round(1)
        order = {"<1R": 0, "1-2R": 1, ">=2R": 2, "clear": 3}
        g = g.sort_values(["cls", "bucket"], key=lambda s: s.map(order) if s.name == "bucket" else s)
        print(f"\n{title}"); print(g.round(2).to_string(index=False))

    ok = df[df["cls"].isin(["HARD", "SOFT", "CLEAR"])]
    table(ok, "ALL families — class × room bucket")
    for fam in ("POS", "SWG"):
        table(ok[ok["family"] == fam], f"{fam} — class × room bucket")

    # symbol-block bootstrap: SOFT <1R vs SOFT >=2R mean R
    soft = ok[ok["cls"] == "SOFT"]
    lo, hi = soft[soft["bucket"] == "<1R"], soft[soft["bucket"] == ">=2R"]
    if len(lo) > 5 and len(hi) > 5:
        rng = np.random.default_rng(7)
        syms_lo, syms_hi = lo["Symbol"].unique(), hi["Symbol"].unique()
        diffs = []
        for _ in range(a.boot):
            sl_ = rng.choice(syms_lo, len(syms_lo)); sh_ = rng.choice(syms_hi, len(syms_hi))
            ml = pd.concat([lo[lo["Symbol"] == s] for s in sl_])["R"].mean()
            mh = pd.concat([hi[hi["Symbol"] == s] for s in sh_])["R"].mean()
            diffs.append(ml - mh)
        d_ = np.array(diffs)
        print(f"\nSOFT <1R minus SOFT >=2R mean R: {lo['R'].mean() - hi['R'].mean():+.3f}R  "
              f"CI95 [{np.percentile(d_, 2.5):+.3f}, {np.percentile(d_, 97.5):+.3f}]  "
              f"(n {len(lo)} vs {len(hi)}, symbol-block, {a.boot} resamples)")
    # soft first obstacle but a HARD one further: room to the hard one
    sh = ok[(ok["cls"] == "SOFT") & ok["hard_room_r"].notna()]
    if len(sh):
        sh = sh.assign(hb=sh["hard_room_r"].apply(bucket))
        g = sh.groupby("hb").agg(n=("R", "size"), hit_t1=("hit_t1", "mean"), mean_R=("R", "mean")).reset_index()
        g["hit_t1"] = (g["hit_t1"] * 100).round(1)
        print("\nSOFT-first trades, bucketed by room to the first HARD obstacle instead:")
        print(g.round(2).to_string(index=False))
    print(f"\nper-trade: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""log_analytics.py - the Reviewer Log as the system's backtest (2-Oct-2026, Jay).

"The reviewer log is the real-world reflection of our trading system; we should base our
backtests on it and use the output to refine the ecosystem."

For every DISTINCT trigger in logs/ai_review_log.csv (review_priority.pick: one per symbol +
TF + trigger bar, S4 alert > board > manual), this joins:
  FEATURES  what S4 showed at that moment, parsed from the review's saved panel read
            (stage, weekly/daily trend, RRG, location, extension from EMA20, RV, bar, pattern,
            setup, room, plan type, risk %, OI state, market regime, trend grade, ruling, TF,
            bar-of-day ...)
  OUTCOME   what happened next, from entry_shadow.py: S4's plan as written (V_plan; V_close
            if the plan did not fill), in R at 5 and 10 sessions, stop-out, best/worst excursion
and reports, PER TIER, how every bucket of every feature performed against the tier average.

A bucket is flagged a CANDIDATE only when n >= MIN_N, its mean R differs from the tier's by
>= GAP_R, and the sign holds in BOTH halves of the Log (earlier and later triggers). A
candidate is a hypothesis, not a rule: it is pre-registered and confirmed on Log rows that
arrive AFTER it was flagged before anything changes. Nothing here edits the live system.

    python log_analytics.py      writes reports/log_analytics.csv and docs/portal/33_live_record.html
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs", "ai_review_log.csv")
SHADOW = os.path.join(HERE, "logs", "entry_shadow.csv")
OUT_CSV = os.path.join(HERE, "reports", "log_analytics.csv")
OUT_HTML = os.path.join(HERE, "docs", "portal", "33_live_record.html")
MIN_N, GAP_R = 15, 0.30

import review_priority as rp   # noqa: E402


# ── features from the panel read ──────────────────────────────────────────────
def _row(panel: str, key: str) -> str:
    m = re.search(r"^%s\s*\|\s*(.*)$" % re.escape(key), panel, re.M)
    return m.group(1).strip() if m else ""


def _num(s: str, pat: str):
    m = re.search(pat, s)
    try:
        return float(m.group(1)) if m else None
    except Exception:
        return None


def _bucket(v, edges, labels):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    for e, l in zip(edges, labels):
        if v < e:
            return l
    return labels[-1]


def features(md_path: str, row) -> dict:
    try:
        txt = open(os.path.join(HERE, md_path), encoding="utf-8").read()
    except Exception:
        return {}
    panel = txt.split("## PANEL READ", 1)[-1]
    f = {}
    sb = _row(panel, "Structure basis")
    m = re.search(r"Stage (\d)", sb); f["stage"] = "Stage %s" % m.group(1) if m else "n/a"
    m = re.search(r"\bW\s*(⬆️|⬇️|➡️)", sb); f["weekly_trend"] = {"⬆️": "up", "⬇️": "down", "➡️": "sideways"}.get(m.group(1) if m else "", "n/a")
    m = re.search(r"\bD\s*(⬆️|⬇️|➡️)", sb); f["daily_trend"] = {"⬆️": "up", "⬇️": "down", "➡️": "sideways"}.get(m.group(1) if m else "", "n/a")
    rr = _row(panel, "RRG (N500 / " + (re.search(r"RRG \(N500 / ([^)]*)\)", panel).group(1) if re.search(r"RRG \(N500 / ([^)]*)\)", panel) else "") + ")")
    m = re.search(r"\b(LEADING|WEAKENING|LAGGING|IMPROVING)\b", rr or panel); f["rrg"] = m.group(1) if m else "n/a"
    zones = _row(panel, "Zones (MTF)")
    f["zone_state"] = ("in demand" if "IN DEMAND" in zones else "in supply" if "IN SUPPLY" in zones
                       else "reacting" if "REACTING" in zones else "between" if zones else "n/a")
    loc = _row(panel, "Location (L)")
    f["location"] = ("pattern zone" if "pattern zone" in loc.lower() else "pivot" if "pivot" in loc.lower()
                     else "none" if loc.upper().startswith("NOT") else (loc.split("—")[0].strip()[:24] or "n/a"))
    ema = _row(panel, "Price vs EMA20 (D)")
    x = _num(ema, r"([+\-]?\d+\.\d+)×ATR")
    f["ext_atr"] = _bucket(x, [0, 1, 2, 3], ["below EMA20", "0-1 ATR", "1-2 ATR", "2-3 ATR", "3+ ATR"])
    rv = _num(_row(panel, "Volume (V) · RV 75") or _row(panel, "Volume (V) · RV 125") or _row(panel, "Volume (V) · RV D") or "", r"(\d+\.\d+)")
    if rv is None:
        m = re.search(r"Volume \(V\) · RV \S+ \|\s*\S*?(\d+\.\d+)", panel); rv = float(m.group(1)) if m else None
    f["rv"] = _bucket(rv, [0.5, 1.0, 1.5, 2.5], ["<0.5", "0.5-1.0", "1.0-1.5", "1.5-2.5", "2.5+"])
    f["bar"] = "OK" if "🟢OK" in _row(panel, "Bar (B)") else ("weak" if _row(panel, "Bar (B)") else "n/a")
    pa = _row(panel, "PRICE ACTION")
    f["pattern"] = (pa.split("[")[0].strip()[:30] or "n/a") if pa else "n/a"
    st = _row(panel, "Setup")
    m = re.search(r"\b(PULLBACK|BREAKOUT|RECOVERY|ACCUMULATION|CONTINUATION|REVERSAL)\b", st); f["setup"] = m.group(1).lower() if m else "n/a"
    m = re.search(r"TREND (A\+ pending|A\+|B|C|F|-)", st); f["trend_grade"] = m.group(1) if m else "n/a (pre 2-Oct)"
    room = _num(_row(panel, "Room for Trade"), r"([+\-]?\d+\.\d+)%")
    f["room"] = _bucket(room, [2, 5, 10], ["<2%", "2-5%", "5-10%", "10%+"])
    plan = _row(panel, "Plan")
    f["plan_type"] = "positional" if "POSITIONAL" in plan else "swing" if "SWING" in plan else "n/a"
    risk = _num(_row(panel, "Entry · SL · T1 · T2"), r"SL [\d.]+ \(−?(\d+\.\d+)%\)")
    f["risk_pct"] = _bucket(risk, [1, 2, 3.5, 6], ["<1%", "1-2%", "2-3.5%", "3.5-6%", "6%+"])
    oi = _row(panel, "FUTURES OI STATE")
    f["oi_state"] = (oi.split("(")[0].strip()[:24] or "n/a") if oi else "n/a"
    mac = _row(panel, "MACRO / SECTOR")
    f["regime"] = (mac.split("·")[0].strip()[:12] or "n/a") if mac else "n/a"
    f["tf"] = str(row["tf"])
    f["bar_of_day"] = str(row.get("trigger_bar", "")).split("|")[-1]
    ru = str(row.get("ai_ruling", "")).upper()
    f["ruling"] = "TAKE" if "TAKE" in ru else "WAIT" if "WAIT" in ru else "PASS" if "PASS" in ru else "NO TRADE" if "NO" in ru else "n/a"
    return f


# ── join + analyse ────────────────────────────────────────────────────────────
def build() -> pd.DataFrame:
    log = rp.pick(pd.read_csv(LOG, dtype=str, keep_default_na=False))
    sh = pd.read_csv(SHADOW) if os.path.exists(SHADOW) else pd.DataFrame()
    rows = []
    for _, r in log.iterrows():
        f = features(str(r.get("file", "")), r)
        if not f:
            continue
        o = {}
        if not sh.empty:
            m = sh[(sh["ts"].astype(str) == str(r["ts"])) & (sh["symbol"].astype(str) == str(r["symbol"]))
                   & (sh["tf"].astype(str).str.replace("1D", "D") == str(r["tf"]).replace("1D", "D"))
                   & (sh["status"] == "scored")]
            pick = m[m["variant"] == "V_plan"]
            if pick.empty:
                pick = m[m["variant"] == "V_close"]
            if not pick.empty:
                p = pick.iloc[0]
                o = {k: p.get(k) for k in ("R5", "R10", "MAE_R", "MFE_R", "stopped")}
        rows.append(dict(ts=r["ts"], symbol=r["symbol"], tier=int(r["tier"]), source=r.get("source", ""), **f, **o))
    return pd.DataFrame(rows)


def analyse(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    out, cands = [], []
    hz = "R10" if "R10" in df and df["R10"].notna().sum() >= 30 else "R5"
    feats = [c for c in df.columns if c not in ("ts", "symbol", "tier", "source", "R5", "R10", "MAE_R", "MFE_R", "stopped")]
    for t in sorted(df["tier"].unique()):
        d = df[(df["tier"] == t) & df[hz].notna()].copy() if hz in df else pd.DataFrame()
        if d.empty:
            continue
        d = d.sort_values("ts")
        half = d["ts"].iloc[len(d) // 2]
        base = d[hz].mean()
        for f in feats:
            for b, g in d.groupby(f):
                e, l = g[g["ts"] < half], g[g["ts"] >= half]
                row = {"tier": rp.LABEL.get(int(t), t), "feature": f, "bucket": b, "n": len(g),
                       "meanR": round(g[hz].mean(), 3), "medR": round(g[hz].median(), 3),
                       "stop%": round(100 * g["stopped"].astype(bool).mean(), 0) if "stopped" in g else np.nan,
                       "MFE": round(g["MFE_R"].mean(), 2) if "MFE_R" in g else np.nan,
                       "vs_tier": round(g[hz].mean() - base, 3), "early": round(e[hz].mean(), 3) if len(e) else np.nan,
                       "late": round(l[hz].mean(), 3) if len(l) else np.nan, "horizon": hz}
                row["candidate"] = bool(len(g) >= MIN_N and abs(row["vs_tier"]) >= GAP_R and len(e) and len(l)
                                        and np.sign(e[hz].mean() - base) == np.sign(l[hz].mean() - base) == np.sign(row["vs_tier"]))
                out.append(row)
                if row["candidate"]:
                    cands.append(row)
    return pd.DataFrame(out), cands


# ── page ──────────────────────────────────────────────────────────────────────
def page(df, tab, cands) -> str:
    e = html.escape
    hz = tab["horizon"].iloc[0] if len(tab) else "R5"
    n_out = int(df[hz].notna().sum()) if hz in df else 0
    css = ("body{font:15px/1.55 Georgia,serif;max-width:1100px;margin:24px auto;padding:0 18px;color:#1d1d1f;background:#fbfaf7}"
           "h1{font:700 30px Archivo,Arial,sans-serif;margin:0 0 6px}h2{font:600 19px Archivo,Arial,sans-serif;margin:28px 0 8px}"
           "table{border-collapse:collapse;width:100%;font:13px 'IBM Plex Mono',monospace}td,th{border-bottom:1px solid #e3e0d8;padding:4px 8px;text-align:left}"
           ".pos{color:#1f7a3a}.neg{color:#a33}.c{background:#fff4d6}.note{background:#f1efe8;padding:10px 14px;border-left:3px solid #b08d2c;margin:12px 0}"
           "@media (prefers-color-scheme:dark){body{background:#16161a;color:#e8e6e1}td,th{border-color:#333}.note{background:#222}.c{background:#3a3220}}")
    L = ['<meta charset="utf-8"><title>The Live Record</title><style>%s</style>' % css,
         "<h1>The Live Record</h1>",
         "<p>The Reviewer Log as the system's backtest. Every distinct trigger (one per symbol, timeframe and trigger bar; "
         "S4 alert &gt; board &gt; manual), what S4 showed at that moment, and what S4's plan earned afterwards, in R at %s. "
         "Rebuilt nightly by the auto-pilot. Generated %s.</p>" % (hz, dt.datetime.now().strftime("%d %b %Y %H:%M")),
         '<div class="note"><b>How to use it.</b> A <b>candidate</b> (highlighted) is a bucket with n &ge; %d whose mean R '
         "is at least %.2fR from its tier's, in the same direction in the earlier and later halves of the Log. It is a "
         "hypothesis: pre-register it and confirm it on triggers that arrive after it was flagged before any rule changes. "
         "Outcomes so far: %d triggers scored.</div>" % (MIN_N, GAP_R, n_out)]
    L.append("<h2>Candidates</h2>")
    if cands:
        L.append("<table><tr><th>tier</th><th>feature</th><th>bucket</th><th>n</th><th>mean R</th><th>vs tier</th><th>early</th><th>late</th></tr>")
        for c in cands:
            L.append("<tr class=c><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%+.2f</td><td class=%s>%+.2f</td><td>%+.2f</td><td>%+.2f</td></tr>" % (
                e(c["tier"]), e(c["feature"]), e(str(c["bucket"])), c["n"], c["meanR"], "pos" if c["vs_tier"] > 0 else "neg",
                c["vs_tier"], c["early"], c["late"]))
        L.append("</table>")
    else:
        L.append("<p>None yet — no bucket clears n &ge; %d with a stable gap. That is the expected state while the Log is young.</p>" % MIN_N)
    for t, g in tab.groupby("tier", sort=False):
        L.append("<h2>%s</h2>" % e(str(t)))
        for f, gf in g.groupby("feature", sort=False):
            L.append("<p><b>%s</b></p><table><tr><th>bucket</th><th>n</th><th>mean R</th><th>median R</th><th>stop%%</th><th>MFE</th><th>vs tier</th></tr>" % e(f))
            for _, r in gf.sort_values("n", ascending=False).iterrows():
                L.append("<tr%s><td>%s</td><td>%d</td><td>%+.2f</td><td>%+.2f</td><td>%s</td><td>%s</td><td class=%s>%+.2f</td></tr>" % (
                    " class=c" if r["candidate"] else "", e(str(r["bucket"])), r["n"], r["meanR"], r["medR"],
                    "" if pd.isna(r["stop%"]) else "%.0f" % r["stop%"], "" if pd.isna(r["MFE"]) else "%.2f" % r["MFE"],
                    "pos" if r["vs_tier"] > 0 else "neg", r["vs_tier"]))
            L.append("</table>")
    return "\n".join(L)


def main() -> int:
    df = build()
    if df.empty:
        print("log analytics: no triggers")
        return 0
    tab, cands = analyse(df)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV.replace(".csv", "_triggers.csv"), index=False)
    tab.to_csv(OUT_CSV, index=False)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(OUT_HTML, page(df, tab, cands))
    except Exception:
        open(OUT_HTML, "w", encoding="utf-8").write(page(df, tab, cands))
    hz = tab["horizon"].iloc[0] if len(tab) else "R5"
    print("log analytics: %d triggers, %d with outcomes (%s), %d candidate(s) -> %s" % (
        len(df), int(df[hz].notna().sum()) if hz in df else 0, hz, len(cands), os.path.relpath(OUT_HTML, HERE)))
    for c in cands:
        print("  CANDIDATE %s · %s = %s  n=%d  %+.2fR vs tier (early %+.2f, late %+.2f)" % (
            c["tier"], c["feature"], c["bucket"], c["n"], c["vs_tier"], c["early"], c["late"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

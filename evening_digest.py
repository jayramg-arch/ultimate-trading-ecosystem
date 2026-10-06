"""evening_digest.py - the post-auto-pilot Telegram (3-Oct-2026, Jay). Auto-pilot Phase 14,
the last thing the run does.

Did the plumbing work today? Each line is something that has failed silently before:
  * auto-pilot phases that were not OK (pipeline_status.json);
  * the three GM boards - 5/5 GOs on the right clock, ⧖D fallbacks, F? fetch failures, age;
  * the reviewer today - reviews done vs FAILED;
  * the trade log - TAKE pool vs taken;
  * S4 bindings per tab (tv_bind_s4 --check) - two tabs sat at 0/32 for a night on 2 Oct;
  * alerts - both S4 GO alerts present, which list, and whether they run the chart's
    compiled version; zone-approach alerts and their seed;
  * exit review - how many holdings sit at/below their Chandelier (the names go out in the
    morning digest).

    python evening_digest.py           build + send
    python evening_digest.py --print   build, print, send nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import pandas as pd

from digest_common import HERE, alert_status, bind_status, exit_review, now_ist, send


def pipeline_lines() -> list[str]:
    try:
        d = json.load(open(os.path.join(HERE, "pipeline_status.json"), encoding="utf-8"))
    except Exception as e:
        return ["AUTO-PILOT: status unreadable (%s)" % e]
    started = str(d.get("started_at") or "")[:16].replace("T", " ")
    bad = [p for p in d.get("phases", []) if p.get("status") != "OK"]
    out = ["AUTO-PILOT %s → %s · %d phases · %d not OK" % (started, str(d.get("ended_at") or "running")[11:16],
                                                          len(d.get("phases", [])), len(bad))]
    if started[:10] != now_ist().date().isoformat():
        out.append("  ⚠ last run is NOT today's")
    for p in bad:
        out.append("  %s %s — %s" % (p.get("status"), str(p.get("name"))[:38], str(p.get("message") or "")[:90]))
    return out


def board_lines() -> list[str]:
    out = ["BOARDS"]
    # 6-Oct-2026: one row per board per day into logs/board_counts_history.csv, so a quiet
    # evening reads against the last few weeks instead of against memory.
    try:
        import board_history as _bh
        _hist = _bh.record()
    except Exception as e:
        _bh, _hist = None, None
        out.append("  (board history not recorded: %s)" % str(e)[:60])
    for tf in ("Daily", "125m", "75m"):
        p = os.path.join(HERE, "gm_board_cache_%s.csv" % tf)
        if not os.path.exists(p):
            out.append("  %-5s not built" % tf)
            continue
        d = pd.read_csv(p)
        s = d["S4-GO"].astype(str)
        go = d.loc[s.str.startswith("5/5"), "Symbol"].astype(str).tolist()
        age = (time.time() - os.path.getmtime(p)) / 3600
        flags = []
        for tag, lab in (("⧖D", "daily-fallback"), ("F?", "fundamentals unread")):
            n = int(s.str.contains(tag, regex=False).sum())
            if n:
                flags.append("%d %s" % (n, lab))
        out.append("  %-5s %d × 5/5%s%s · %.0fh old%s%s" % (tf, len(go), (": " + ", ".join(go[:8])) if go else "",
                                                     " …" if len(go) > 8 else "", age, (" · " + ", ".join(flags)) if flags else "",
                                                     _bh.compare(tf, _hist) if _bh is not None else ""))
    return out


def reviewer_lines() -> list[str]:
    today = now_ist().date().isoformat()
    ok = failed = 0
    p = os.path.join(HERE, "logs", "s4_alert_review.log")
    try:
        for ln in open(p, encoding="utf-8", errors="replace"):
            if not ln.startswith(today):
                continue
            if "reviewed in" in ln:
                ok += 1
            elif "FAILED" in ln or re.search(r"review rc [1-9]", ln):
                failed += 1
    except Exception:
        pass
    try:
        lg = pd.read_csv(os.path.join(HERE, "logs", "ai_review_log.csv"), dtype=str, keep_default_na=False)
        n_today = int(lg["ts"].str.startswith(today).sum())
    except Exception:
        n_today = 0
    out = ["REVIEWER today: %d Log rows · alert path %d ok / %d FAILED" % (n_today, ok, failed)]
    if failed:
        out.append("  ⚠ failures - see logs/s4_alert_review.log (a second provider would cover a Gemini outage)")
    return out


def trade_log_line() -> list[str]:
    try:
        import trade_log
        _df, s = trade_log.build()
        return ["TRADE LOG: " + trade_log.summary_line(s)]
    except Exception as e:
        return ["TRADE LOG: unavailable (%s)" % str(e)[:80]]


def tv_lines() -> list[str]:
    out = ["S4 BINDINGS"] + (bind_status() or ["  no S4 tab found"])
    a = alert_status()
    if a.get("err"):
        return out + ["ALERTS: not checked (%s)" % a["err"][:80]]
    s4 = a.get("s4") or []
    cur = a.get("chart_ver")
    out.append("ALERTS: %d S4 GO alert(s) · chart S4 version %s" % (len(s4), cur))
    for x in s4:
        drift = "" if (cur is None or str(x.get("ver")) == str(cur)) else "  ⚠ runs %s - recreate after a GO-logic change" % x.get("ver")
        out.append("  %sm %s %s%s%s" % (x.get("res"), "on" if x.get("active") else "OFF", x.get("sym"),
                                       drift, ("  error: %s" % x["err"]) if x.get("err") else ""))
    if len(s4) < 2:
        out.append("  ⚠ fewer than two S4 GO alerts - recreate on today's GM_Swing list")
    out.append("  zone-approach alerts: %d%s" % (a.get("zone", 0), "" if a.get("seed") else "  ⚠ SEED MISSING - create a price alert named 'GM-POS zone SEED'"))
    return out


def exit_lines() -> list[str]:
    rows, err = exit_review()
    if err:
        return ["EXIT REVIEW: not available (%s)" % err[:80]]
    return ["EXIT REVIEW: %d holding(s) at/below their Chandelier%s" % (
        len(rows), (" - " + ", ".join(r["sym"] for r in rows)) if rows else "")]


def build() -> str:
    L = ["EVENING · %s" % now_ist().strftime("%a %d %b %Y %H:%M IST"), ""]
    for part in (pipeline_lines, board_lines, reviewer_lines, trade_log_line, tv_lines, exit_lines):
        try:
            L += part()
        except Exception as e:
            L.append("%s: failed (%s)" % (part.__name__, str(e)[:80]))
        L.append("")
    return "\n".join(L).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    txt = build()
    print(txt)
    if not a.print:
        print("sent" if send(txt) else "NOT SENT (Telegram) - copy in reports/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""digest_common.py - shared pieces of the morning and evening Telegram digests (3-Oct-2026).

WHY (audit AUD-OCT-01): the stop-trail job ran every day from 11 Sep, exited 0, and never
moved a single stop - every modify was refused by Dhan (DH-905, Invalid IP). Nothing read
its log. The digests exist so a whole class of "ran, reported success, did nothing" faults
reaches Jay's phone the same day: one message in the morning (what to act on) and one after
the auto-pilot (did the plumbing work).

Everything here is READ-ONLY: it reads Dhan (holdings, GTT legs), TradingView over CDP and
the project's own files. It places, modifies and deletes nothing.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST).replace(tzinfo=None)


def send(text: str) -> bool:
    """Telegram, chunked; also written to reports/ so a failed send is never the only copy."""
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    stamp = now_ist().strftime("%Y%m%d_%H%M")
    kind = "morning" if "MORNING" in text[:40] else "evening"
    with open(os.path.join(HERE, "reports", f"digest_{kind}_{stamp}.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    try:
        import s4_review
        return bool(s4_review.telegram(text))
    except Exception as e:
        print("telegram failed: %s" % e)
        return False


def exit_review() -> tuple[list[dict], str | None]:
    """Positions whose catalyst-aware Chandelier is at or above the last price - the
    trail engine's own 'breached' list (gtt_auto_shield.build_trail_proposals), read-only.
    One row per SYMBOL (a symbol can carry two OCO legs; the stop shown is the higher)."""
    try:
        import gtt_auto_shield as g
        _props, breached, err = g.build_trail_proposals()
    except Exception as e:
        return [], "exit review unavailable: %s" % e
    if err:
        return [], err
    rows = {}
    for sym, old, ch, ltp in breached:
        r = rows.get(sym)
        if r is None or old > r["stop"]:
            rows[sym] = {"sym": sym, "stop": float(old), "ce": float(ch), "ltp": float(ltp),
                         "below_ce_pct": (float(ltp) / float(ch) - 1.0) * 100.0 if ch else 0.0,
                         "to_stop_pct": (float(old) / float(ltp) - 1.0) * 100.0 if ltp else 0.0}
    return sorted(rows.values(), key=lambda r: r["below_ce_pct"]), None


def exit_review_lines(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        out.append("  %-11s LTP %9.2f  CE %9.2f (%+.1f%%)  stop %9.2f (%+.1f%% away)" % (
            r["sym"], r["ltp"], r["ce"], r["below_ce_pct"], r["stop"], r["to_stop_pct"]))
    return out


def market_line() -> str:
    try:
        import market_context
        return " · ".join(market_context.parts())
    except Exception:
        return ""


def bind_status() -> list[str]:
    """tv_bind_s4 --check, condensed to one line per S4 tab. Empty when TradingView is down."""
    try:
        r = subprocess.run([PY, os.path.join(HERE, "tv_bind_s4.py"), "--check"], capture_output=True,
                           text=True, timeout=120, encoding="utf-8", errors="replace")
    except Exception as e:
        return ["bindings: check failed (%s)" % e]
    out, cid = [], None
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"chart (\w+): (.*)", ln)
        if m:
            cid = m.group(1)
            continue
        m = re.match(r"\s+bound (\d+) · unbound (\d+)", ln)
        if m and cid:
            b, u = int(m.group(1)), int(m.group(2))
            out.append("  %s %s: %d/%d bound" % ("OK  " if u == 0 else "FAIL", cid, b, b + u))
    if not out and "debug port" in (r.stderr or ""):
        return ["  TradingView not reachable (debug port) - bindings not checked"]
    return out


ALERTS_JS = r"""
(async () => {
  try {
    const W = window.webpackChunktradingview;
    if (!window.__tvReq) W.push([["digest" + Date.now()], {}, r => { window.__tvReq = r; }]);
    let modId = null;
    for (const c of W) { const m = c[1] || {}; for (const k in m) { let s; try { s = m[k].toString(); } catch (e) { continue; }
      if (s.indexOf('"Alerts.AlertsRestApi"') >= 0 && s.indexOf("getAlertsRestApi") >= 0) { modId = k; break; } } if (modId) break; }
    const api = window.__tvReq(modId).getAlertsRestApi();
    const la = await api.listAlerts();
    const chart = (window.TradingViewApi || window.tvWidget).activeChart();
    const st = chart.getAllStudies().find(s => s.name.indexOf("Section 4") === 0);
    let cur = null; try { cur = chart.getStudyById(st.id)._study.metaInfo().pine.version; } catch (e) {}
    const s4 = la.filter(a => a.condition && a.condition.type === "alert_cond" && String(a.message || "").indexOf("S4 GO") >= 0);
    return JSON.stringify({chart_ver: cur,
      s4: s4.map(a => ({res: a.resolution, active: a.active, ver: a.condition.series[0].pine_version,
                        sym: (String(a.symbol).match(/WATCHLIST:\d+/) || [""])[0], err: a.last_error})),
      zone: la.filter(a => String(a.name || "").indexOf("GM-POS zone ") === 0 && a.name !== "GM-POS zone SEED").length,
      seed: la.some(a => a.name === "GM-POS zone SEED")});
  } catch (e) { return JSON.stringify({err: String(e)}); }
})()
"""


def alert_status() -> dict:
    try:
        from tv_gm_alerts import _eval
        from tv_bind_s4 import _chart_targets_all
        t = _chart_targets_all()
        if not t:
            return {"err": "TradingView not reachable"}
        for tg in t:
            raw = _eval(tg["webSocketDebuggerUrl"], ALERTS_JS)
            d = json.loads(raw) if raw else {}
            if d.get("chart_ver") or d.get("s4"):
                return d
        return d
    except Exception as e:
        return {"err": str(e)}

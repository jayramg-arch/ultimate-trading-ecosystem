"""Positional "price is nearing its Daily zone" alerts, refreshed nightly (2-Oct-2026, Jay).

WHY: TradingView's plan allows two WATCHLIST alerts and both now time the SWING clock
(75m + 125m on GM_Swing). Positional names are alerted by the evening Daily-board review,
which says nothing while price is still travelling towards a zone. Single-symbol PRICE
alerts do not count against the watchlist quota, so each positional name that sits
above a Daily+ demand zone gets one: "price is within NEAR_PCT of the zone". It is an
APPROACH notice, not a trigger - the GO is still read on the Daily close.

WHAT, each evening (auto-pilot Phase 12b2, after the Daily board is rebuilt):
  * candidates = Daily board rows with plan type POSITIONAL, not blocked (no ⛔), whose
    nearest demand zone is between MIN_PCT and MAX_PCT below the price (the board's
    →Zone column; a name already AT its zone needs no approach alert);
  * alert level = zone top x (1 + NEAR_PCT/100), crossing DOWN, once, expiring in
    EXPIRY_DAYS; at most MAX_ALERTS, best Overall first;
  * yesterday's set is replaced: only alerts whose NAME starts with PREFIX are deleted,
    and only after the new set is built. Nothing else on the account is touched.

Built through TradingView's own alerts client inside the logged-in page (the
tv_gm_alerts.py route). createAlert is refused from the page (invalid_request on every
payload tried, 2-Oct-2026), but cloneAlerts and modifyRestartAlert work, so ONE permanent
price alert named SEED is cloned per name and each clone modified to its symbol, level and
expiry, then read back. The seed lives on the account for good; if it is ever deleted,
create any price alert by hand and rename it "GM-POS zone SEED". Symbols use the stock's
native INR series - the official MCP connector created USD-converted ones.

    python tv_zone_alerts.py --dry-run   # list what would be set
    python tv_zone_alerts.py             # replace yesterday's set
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PREFIX = "GM-POS zone "      # identifies OUR alerts; nothing without it is ever deleted
SEED = "GM-POS zone SEED"    # the one permanent alert that is cloned (never deleted)
NEAR_PCT = 1.0               # alert when price is within this % of the zone top
MIN_PCT = 1.5                # closer than this: already effectively at the zone
MAX_PCT = 12.0               # further than this: not arriving in the alert's lifetime
MAX_ALERTS = 40
EXPIRY_DAYS = 7
BOARD = os.path.join(HERE, "gm_board_cache_Daily.csv")
LOG = os.path.join(HERE, "logs", "tv_zone_alerts.log")


def _log(msg: str) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def _tv_symbol(sym: str) -> str:
    """TradingView turns '-' into '_' (NAM-INDIA -> NAM_INDIA) but KEEPS '&' (NSE:M&MFIN is the
    live chart symbol - db_portfolio_sync.normalize_ticker, verified 10-Sep-2026)."""
    return "NSE:" + sym.strip().upper().replace("-", "_")


def candidates() -> tuple[list[dict], str]:
    import pandas as pd
    if not os.path.exists(BOARD):
        return [], "no Daily board cache"
    age_h = (time.time() - os.path.getmtime(BOARD)) / 3600
    df = pd.read_csv(BOARD)
    note = "Daily board %.1fh old" % age_h + (" - STALE, rebuild it" if age_h > 30 else "")
    plan = df["Plan"] if "Plan" in df.columns else None
    out = []
    for i, r in df.iterrows():
        sym = str(r.get("Symbol") or "").strip()
        go = str(r.get("S4-GO") or "")
        if not sym or go.startswith("⛔"):
            continue
        pt = str(plan.iloc[i]) if plan is not None else ""
        if pt not in ("positional", "swing"):
            import commander_core as cc
            pt = cc.plan_type_for_symbol(sym) or ""
        if pt != "positional":
            continue
        try:
            pct = float(r.get("→Zone"))
            cmp_ = float(r.get("CMP"))
        except (TypeError, ValueError):
            continue
        if not (MIN_PCT <= pct <= MAX_PCT) or cmp_ <= 0:
            continue
        zone = cmp_ * (1 - pct / 100.0)
        level = round(zone * (1 + NEAR_PCT / 100.0), 2)
        if level >= cmp_:
            continue
        loc = str(r.get("Loc") or "")
        m = re.search(r"pattern ([DWM])", loc)
        out.append({"sym": sym, "tv": _tv_symbol(sym), "level": level, "zone": round(zone, 2),
                    "pct": pct, "tf": m.group(1) if m else "?", "cmp": cmp_,
                    "overall": float(r.get("Overall") or 0)})
    out.sort(key=lambda c: -c["overall"])
    return out[:MAX_ALERTS], note


JS = r"""
(async () => {
  const cfg = __CFG__;
  const out = {created: [], deleted: 0, failed: [], kept_foreign: 0};
  try {
    const W = window.webpackChunktradingview;
    if (!W) return JSON.stringify({err: "TradingView module loader not found"});
    if (!window.__tvReq) W.push([["gmzone" + Date.now()], {}, r => { window.__tvReq = r; }]);
    let modId = null;
    for (const c of W) { const m = c[1] || {}; for (const k in m) { let s; try { s = m[k].toString(); } catch (e) { continue; }
      if (s.indexOf('"Alerts.AlertsRestApi"') >= 0 && s.indexOf("getAlertsRestApi") >= 0) { modId = k; break; } } if (modId) break; }
    if (!modId || !window.__tvReq) return JSON.stringify({err: "TradingView alerts client not found"});
    const api = window.__tvReq(modId).getAlertsRestApi();
    const la = (await api.listAlerts()) || [];
    // SEED: createAlert is refused from the page (invalid_request, measured 2-Oct), but
    // clone + modify both work - so one permanent price alert named cfg.seed is cloned
    // per name and each clone is modified to its symbol and level. Never deleted here.
    const seeds = la.filter(a => a.name === cfg.seed).sort((x, y) => String(x.create_time).localeCompare(String(y.create_time)));
    const seed = seeds[0];
    const ours = la.filter(a => String(a.name || "").indexOf(cfg.prefix) === 0 && a.name !== cfg.seed);
    out.kept_foreign = la.length - ours.length - seeds.length;
    out.old = ours.length;
    if (!seed) return JSON.stringify(Object.assign(out, {err: "no seed alert named '" + cfg.seed + "' - create ANY price alert once and rename it to that (see the module docstring)"}));
    if (cfg.dry) return JSON.stringify(out);
    const exp = new Date(Date.now() + cfg.days * 86400000).toISOString().replace(/\.\d+Z$/, "Z");
    const mk = (id, sym, level, name, msg, push, ex) => {
      const cond = {type: "cross_down", frequency: "on_first_fire", cross_interval: true, resolution: "1",
                    series: [{type: "barset"}, {type: "value", value: level}]};
      return {alert_id: id, symbol: '={"adjustment":"splits","symbol":"' + sym + '"}', resolution: "1",
              condition: cond, message: msg, web_hook: null, name: name, popup: push, email: false,
              sms_over_email: false, mobile_push: push, sound_file: null, sound_duration: 0,
              expiration: ex, auto_deactivate: true, cross_interval: true, active: true, ignore_warnings: true};
    };
    // duplicate seeds (from an earlier clone that failed to rename) are removed
    if (seeds.length > 1) { try { await api.deleteAlerts({alert_ids: seeds.slice(1).map(a => a.alert_id)}); } catch (e) {} }
    for (const c of cfg.items) {
      let newId = null;
      try {
        const cl = await api.cloneAlerts({alert_ids: [seed.alert_id]});
        newId = cl && cl[0] && cl[0].alert_id;
        if (!newId) throw new Error("clone returned no id");
        const msg = c.sym + " is within " + cfg.near + "% of its " + c.tf + " demand zone (top " + c.zone +
                    "). Positional: an approach notice, not a trigger - read the Daily close.";
        await api.modifyRestartAlert(mk(newId, c.tv, c.level, cfg.prefix + c.sym, msg, true, exp));
        const chk = ((await api.getAlerts({alert_ids: [newId]})) || [])[0];
        const v = chk && chk.condition && chk.condition.series && chk.condition.series[1] && chk.condition.series[1].value;
        if (!chk || String(chk.symbol).indexOf(c.tv) < 0 || Math.abs(v - c.level) > 0.01) throw new Error("verify failed: " + (chk && chk.symbol) + " @ " + v);
        out.created.push(c.sym + "@" + c.level + "#" + newId);
      } catch (e) {
        out.failed.push(c.sym + ": " + String((e && (e.code || e.message)) || e).slice(0, 120));
        if (newId) { try { await api.deleteAlerts({alert_ids: [newId]}); } catch (x) {} }
      }
    }
    // keep the seed alive: push its expiry out (it watches a level it can never reach)
    try { await api.modifyRestartAlert(mk(seed.alert_id, "NSE:SAILIFE", 1, cfg.seed,
            "seed for tv_zone_alerts.py - do not delete", false,
            new Date(Date.now() + 60 * 86400000).toISOString().replace(/\.\d+Z$/, "Z"))); } catch (e) { out.failed.push("seed refresh: " + String((e && e.code) || e)); }
    // delete yesterday's set only AFTER today's was attempted, and only OUR alerts
    if (ours.length) {
      try { await api.deleteAlerts({alert_ids: ours.map(a => a.alert_id)}); out.deleted = ours.length; }
      catch (e) { out.failed.push("delete old: " + String((e && e.message) || e).slice(0, 120)); }
    }
    return JSON.stringify(out);
  } catch (e) { out.err = String(e); return JSON.stringify(out); }
})()
"""


def run(dry: bool = False) -> int:
    items, note = candidates()
    print("Positional zone-approach alerts: %d candidate(s) · %s%s" % (len(items), note, " [dry run]" if dry else ""), flush=True)
    for c in items:
        print("  %-12s %s-zone %10.2f  alert < %10.2f  (CMP %.2f, %.1f%% above the zone)" % (
            c["sym"], c["tf"], c["zone"], c["level"], c["cmp"], c["pct"]))
    from tv_gm_alerts import _eval
    from tv_bind_s4 import _chart_targets_all
    targets = _chart_targets_all()
    if not targets:
        print("ERROR: no TradingView chart tab over CDP - is TradingView running with the debug port?")
        return 2
    cfg = {"prefix": PREFIX, "seed": SEED, "items": items, "near": NEAR_PCT, "days": EXPIRY_DAYS, "dry": bool(dry)}
    raw = _eval(targets[0]["webSocketDebuggerUrl"], JS.replace("__CFG__", json.dumps(cfg)))
    try:
        res = json.loads(raw) if raw else {"err": "no result"}
    except Exception:
        res = {"err": "unparseable: " + str(raw)[:200]}
    if res.get("err"):
        print("ERROR: " + res["err"]); _log("ERROR " + res["err"])
        return 1
    line = "existing %s (of ours) · other alerts untouched %s · created %d · deleted %d · failed %d" % (
        res.get("old"), res.get("kept_foreign"), len(res.get("created", [])), res.get("deleted", 0), len(res.get("failed", [])))
    print(("DRY RUN - " if dry else "") + line)
    for f in res.get("failed", []):
        print("  FAILED " + f)
    _log(line + (" · " + "; ".join(res.get("failed", [])) if res.get("failed") else ""))
    return 1 if res.get("failed") else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return run(dry=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())

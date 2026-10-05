"""Refresh the two S4 GO watchlist alerts (75m + 125m) onto today's GM board list.

WHY (Jay, 30-Sep-2026): the GM board watchlist is date-stamped and rebuilt by the
auto-pilot every evening, and an alert also FREEZES S4's inputs - both bundles - at the
moment it is saved. So the alerts had to be recreated by hand every night, on two
timeframes, or they fired on yesterday's list with yesterday's bundle data.

HOW - no dialog clicking. The TradingView page talks to its own alerts service
(pricealerts.tradingview.com: /list_alerts, /modify_restart_alert, /create_alert,
/delete_alerts - read out of TradingView's own client code on 30-Sep). Running inside
the logged-in page over CDP, this:

  1. lists the alerts and takes the existing S4 GO WATCHLIST alerts as TEMPLATES. They
     carry everything a person set up once: the alertcondition, "once per bar close",
     the message, the webhook, the bound v67/Zigzag studies.
  2. rewrites only what changes daily: the symbol (WATCHLIST:<today's list id>) and
     S4's three pushed inputs - both bundles and the pivot toggle - read from the chart,
     after the evening run has pushed them there. Every other input is left exactly as
     the template has it: a bound source is stored as an internal reference inside the
     alert, and overwriting it from the chart would break the binding.
  3. MODIFIES each alert in place (same alert id, nothing deleted). Only if the service
     refuses a modify does it create a fresh alert - and it deletes an old one only
     after its replacement was created, and only by its own alert_id. There is no
     "delete all" anywhere in this file.

REFUSES, and says why, when there is no template (the first night after an S4 compile:
a recompile deletes the alerts - create them ONCE by hand, the job keeps them fresh from
then on), when today's list does not exist, or when the S4 inputs it needs are missing.

    python tv_gm_alerts.py            # refresh both alerts
    python tv_gm_alerts.py --dry-run  # show what would change, touch nothing
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import websocket  # noqa: E402

from tv_bind_s4 import _chart_targets_all  # noqa: E402
from tv_push_bundles import IN1, IN2, IN3, IN4  # noqa: E402 - the SAME titles the pusher writes

LOG = os.path.join(HERE, "logs", "tv_gm_alerts.log")
os.makedirs(os.path.dirname(LOG), exist_ok=True)
log = logging.getLogger("tv_gm_alerts")
if not log.handlers:
    _h = logging.FileHandler(LOG, encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# Two watchlist alerts is the TradingView plan ceiling (Jay, 2-Oct-2026), so the alerts are
# the SWING clock only. The positional clock is the Daily close, which needs no TradingView
# alert: the 16:30 auto-pilot rebuilds the Daily board and Phase 13 reviews every Daily 5/5
# GO and sends it to Telegram - the same message an alert would have produced, an hour
# after a close that could not be traded until the next session anyway. "D" still works
# here if a Daily S4 GO alert is ever created (a higher plan): add it back to RESOLUTIONS.
RESOLUTIONS = ["75", "125"]
LIST_PREFIX = "Golden_Matcher_Board-"
# PLAN CLOCK (2-Oct-2026, Jay): each alert watches only the names whose plan type
# belongs on its timeframe - positional on the Daily close, swing on 75m/125m. The
# lists are written by run_pipeline Phase 4.8 (FINAL_GM_POSITIONAL / FINAL_GM_SWING)
# and pushed with the rest. If today's split list is missing the alert falls back to
# the full board list and SAYS so - it never goes silent.
PLAN_LISTS = {"75": "GM_Swing-", "125": "GM_Swing-", "D": "GM_Positional-"}
IST = timezone(timedelta(hours=5, minutes=30))


def todays_list_name(prefix: str = LIST_PREFIX) -> str:
    """Golden_Matcher_Board-30SEP26 - the name Phase 7 gives today's list."""
    return prefix + datetime.now(IST).strftime("%d%b%y").upper()


JS = r"""
(async () => {
  const cfg = __CFG__;
  const out = {steps: [], results: []};
  try {
    const U = window.user;
    if (!U || !U.username) return JSON.stringify({err: "not logged in to TradingView"});
    // TradingView's OWN alerts client, found through the page's module loader. A plain
    // fetch() POST to pricealerts failed ("Failed to fetch") - the client goes through
    // TradingView's internal fetch wrapper. Using the client sends exactly what the
    // Alerts dialog sends: same URL, same wrapper, same retries. Located by content, not
    // by module id, so a TradingView update that renumbers modules does not break it.
    const W = window.webpackChunktradingview;
    if (!W) return JSON.stringify({err: "TradingView module loader not found"});
    if (!window.__tvReq) W.push([["gmalerts" + Date.now()], {}, r => { window.__tvReq = r; }]);
    let modId = null;
    for (const c of W) { const m = c[1] || {}; for (const k in m) { let s; try { s = m[k].toString(); } catch (e) { continue; }
      if (s.indexOf('"Alerts.AlertsRestApi"') >= 0 && s.indexOf("getAlertsRestApi") >= 0) { modId = k; break; } } if (modId) break; }
    if (!modId || !window.__tvReq) return JSON.stringify({err: "TradingView alerts client not found (the Alerts panel may need opening once)"});
    const api = window.__tvReq(modId).getAlertsRestApi();
    const call = async (fn, arg) => { try { return {s: "ok", r: await api[fn](arg)}; }
                                       catch (e) { return {s: "error", errmsg: String((e && e.code) || "") + " " + String((e && e.message) || e)}; } };

    // today's GM board list
    const wl = await (await fetch("https://www.tradingview.com/api/v1/symbols_list/custom/",
                                  {credentials: "include"})).json();
    const board = (wl || []).find(l => l.name === cfg.listName);
    // KEEP-LIST mode (3-Oct-2026): --upgrade-version on a day with no new lists (a weekend
    // compile) leaves each alert on the list it already watches and only moves the version.
    const keep = !board && cfg.upgrade;
    if (!board && !keep) return JSON.stringify({err: "watchlist '" + cfg.listName + "' not found - has the auto-pilot pushed today's lists?"});
    // per-timeframe list: the plan-clock split list, else the full board list (said so)
    const listFor = (res) => {
      const want = (cfg.planLists || {})[res];
      const hit = want && (wl || []).find(l => l.name === want);
      if (hit) return {list: hit, note: ""};
      return {list: board, note: want ? " (split list " + want + " MISSING - fell back to the full board)" : ""};
    };
    const norm = (r) => { r = String(r); return (r === "1D" || r === "D") ? "D" : r; };
    out.steps.push(keep ? "no list for today - alerts stay on their current lists (version upgrade only)"
                        : "board list " + cfg.listName + " = WATCHLIST:" + board.id + " (" + (board.symbols || []).length + " symbols)");

    // S4 on this chart: the three inputs the evening run pushes
    const chart = (window.TradingViewApi || window.tvWidget).activeChart();
    const st = chart.getAllStudies().find(s => s.name.indexOf("Section 4") === 0);
    if (!st) return JSON.stringify({err: "S4 is not on this chart tab"});
    const s4 = chart.getStudyById(st.id);
    let curVer = null; try { curVer = s4._study.metaInfo().pine.version; } catch (e) {}
    const ids = {};
    s4.getInputsInfo().forEach(i => { if (cfg.titles.indexOf(i.name) >= 0) ids[i.name] = i.id; });
    const missing = cfg.titles.filter(t => !(t in ids) && (cfg.optional || []).indexOf(t) < 0);
    if (missing.length) return JSON.stringify({err: "S4 input not found: " + missing.join(" / ")});
    const vals = {};
    s4.getInputValues().forEach(v => { vals[v.id] = v.value; });
    const fresh = {};
    cfg.titles.forEach(t => { if (t in ids) fresh[ids[t]] = vals[ids[t]]; });
    if (!String(fresh[ids[cfg.titles[0]]] || "").length)
      return JSON.stringify({err: "bundle 1 is EMPTY on the chart - refusing to put an empty bundle into the alerts"});

    // templates: the existing S4 GO watchlist alerts
    const la = await call("listAlerts");
    if (la.s !== "ok") return JSON.stringify({err: "listAlerts: " + la.errmsg});
    // a.symbol is an ENCODED string: ={"session":"regular","symbol":"WATCHLIST:349004311"}
    const tpls = (la.r || []).filter(a => a.condition && a.condition.type === "alert_cond"
        && String(a.message || "").indexOf("S4 GO") >= 0 && /WATCHLIST:\d+/.test(String(a.symbol || "")));
    // REBUILD SOURCE (5-Oct-2026): deleting the watchlist an alert watches deletes the alert
    // too, so a missing 75m/125m alert is rebuilt from ANY S4 GO alert still on the account
    // (the other watchlist alert, or a per-stock GM-POS GO alert): clone it, then point the
    // clone at the list and the timeframe. Only when no S4 GO alert exists at all (after an
    // S4 compile) does it need a hand-made one.
    const anyS4 = (la.r || []).filter(a => a.condition && a.condition.type === "alert_cond"
        && String(a.message || "").indexOf("S4 GO") >= 0);
    if (!tpls.length && !anyS4.length) return JSON.stringify({err: "no S4 GO alert of any kind to use as a template. After an S4 compile TradingView deletes them - create the 75m and 125m alerts ONCE by hand; this job keeps them fresh from then on."});
    out.steps.push(tpls.length + " template(s): " + tpls.map(a => a.alert_id + "@" + a.resolution).join(", "));

    const strip = ["alert_id", "create_time", "created", "last_fire_time", "last_fired", "last_error",
                   "last_stop_reason", "active", "kinds", "id"];
    for (const res of cfg.resolutions) {
      let tpl = tpls.find(a => norm(a.resolution) === res);
      let rebuilt = "";
      if (!tpl) {
        const src = tpls[0] || anyS4[0];
        if (cfg.dry) { out.results.push({res: res, err: "missing - would be rebuilt from alert " + src.alert_id}); continue; }
        const cl = await call("cloneAlerts", {alert_ids: [src.alert_id]});
        const nid = cl.s === "ok" && cl.r && cl.r[0] && cl.r[0].alert_id;
        if (!nid) { out.results.push({res: res, err: "missing, and cloning alert " + src.alert_id + " failed: " + (cl.errmsg || "no id")}); continue; }
        tpl = JSON.parse(JSON.stringify(src));
        tpl.alert_id = nid; tpl.name = null; tpl.expiration = null; tpl.resolution = res;
        tpl.symbol = '={"session":"regular","symbol":"WATCHLIST:0"}';
        [tpl.condition].concat(tpl.conditions || []).forEach(c => { if (c && "resolution" in c) c.resolution = res; });
        rebuilt = "REBUILT from alert " + src.alert_id + " (the watchlist alert had been deleted)";
      }
      const lf = keep ? null : listFor(res);
      const _curId = tpl ? ((String(tpl.symbol).match(/WATCHLIST:(\d+)/) || [])[1]) : null;
      let list = keep ? ((wl || []).find(l => String(l.id) === String(_curId)) || {id: _curId, name: "current list", symbols: []}) : lf.list;
      if (keep && rebuilt) {     // a rebuilt alert has no list to keep: newest list of its plan clock
        const pre = (cfg.planLists || {})[res] ? String(cfg.planLists[res]).replace(/\d{2}[A-Z]{3}\d{2}$/, "") : "GM_Swing-";
        const cands = (wl || []).filter(l => String(l.name).indexOf(pre) === 0).sort((x, y) => y.id - x.id);
        if (cands.length) list = cands[0];
      }
      const newSym = "WATCHLIST:" + list.id;
      if (!tpl) { out.results.push({res: res, err: "no template on " + res + " - create that S4 GO alert by hand once, on the " + list.name + " list"}); continue; }
      const p = JSON.parse(JSON.stringify(tpl));
      // The inputs live in condition AND in the conditions[] mirror - update every copy.
      const sers = [p.condition].concat(p.conditions || []).map(c => (c && c.series || [])[0]).filter(Boolean);
      const inp = sers.length && sers[0].inputs;
      if (!inp) { out.results.push({res: res, err: "template has no S4 inputs"}); continue; }
      const bad = Object.keys(fresh).filter(k => !(k in inp));
      if (bad.length) { out.results.push({res: res, err: "template lacks inputs " + bad.join(",") + " - S4 was recompiled; recreate by hand once"}); continue; }
      const oldSym = (String(p.symbol).match(/WATCHLIST:\d+/) || [""])[0];
      const before = {sym: oldSym, n: ((p.symbolset_data || {}).symbols || []).length,
                      b1: String(inp[ids[cfg.titles[0]]] || "").length, b2: String(inp[ids[cfg.titles[1]]] || "").length};
      // CLIENT-SHAPED payload (measured 30-Sep): sending the listed alert back whole
      // (~365 KB, with server-derived symbolset_data / presentation_data / complexity)
      // died at the transport as "Fetch Failed". The fields a client sends are ~167 KB and
      // go through; the server derives the symbol snapshot from the list id itself.
      // ignore_warnings = the "this script may repaint" warning the dialog asks you to
      // accept by hand - without it the service answers warning_pine_repainting.
      let row_note = "";
      const KEEP = ["alert_id", "symbol", "resolution", "condition", "message", "web_hook", "name",
                    "popup", "email", "sms_over_email", "mobile_push", "sound_file", "sound_duration",
                    "expiration", "auto_deactivate", "cross_interval", "active"];
      const q = {};
      KEEP.forEach(k => { if (k in p) q[k] = p[k]; });
      q.ignore_warnings = true;
      const qin = q.condition.series[0].inputs;
      // --upgrade-version (3-Oct-2026): an alert keeps the compiled version it was created
      // on, and this refresh copies it along, so a compile that TradingView does not delete
      // the alerts for leaves them running the OLD script. When every input the alert
      // carries still exists on the chart's S4, move it to the chart's version.
      if (cfg.upgrade && curVer && String(q.condition.series[0].pine_version) !== String(curVer)) {
        const chartIds = {}; s4.getInputsInfo().forEach(i => { chartIds[i.id] = 1; });
        const missing = Object.keys(qin).filter(k => !(k in chartIds));
        if (missing.length) { row_note = "version NOT upgraded - " + missing.length + " alert input(s) no longer on the chart; recreate by hand"; }
        else {
          const oldVer = q.condition.series[0].pine_version;
          [q.condition].concat(q.conditions || []).forEach(c => { ((c && c.series) || []).forEach(sr => { if (sr && sr.pine_version) sr.pine_version = curVer; }); });
          row_note = "version " + oldVer + " -> " + curVer;
        }
      }
      Object.keys(fresh).forEach(k => { qin[k] = fresh[k]; });
      q.symbol = String(q.symbol).replace(/WATCHLIST:\d+/, newSym);
      const syms = (list.symbols || []).filter(x => String(x).indexOf("###") !== 0);
      const after = {sym: newSym, n: syms.length, b1: String(fresh[ids[cfg.titles[0]]] || "").length, b2: String(fresh[ids[cfg.titles[1]]] || "").length};
      const row = {res: res, id: tpl.alert_id, before: before, after: after, list: list.name + (lf ? lf.note : " (kept)"), note: (rebuilt ? rebuilt + (row_note ? "; " : "") : "") + row_note};
      if (cfg.dry) { row.action = "dry-run"; out.results.push(row); continue; }

      // 1) modify in place - nothing is deleted
      const mod = await call("modifyRestartAlert", q);
      if (mod.s === "ok") {
        // VERIFY what the service now holds - list, symbol count, bundle - not what we sent.
        const chk = await call("getAlerts", {alert_ids: [tpl.alert_id]});
        const a2 = chk.s === "ok" && (chk.r || [])[0];
        const got = a2 ? {sym: (String(a2.symbol).match(/WATCHLIST:\d+/) || [""])[0],
                          n: ((a2.symbolset_data || {}).symbols || []).length,
                          b1: String(a2.condition.series[0].inputs[ids[cfg.titles[0]]] || "").length,
                          ver: a2.condition.series[0].pine_version} : null;
        if (got && row_note.indexOf(" -> ") > 0) row.note += (String(got.ver) === String(curVer) ? " (verified)" : " (NOT applied: alert still on " + got.ver + ")");
        row.action = got && got.sym === newSym && got.b1 === after.b1 ? "modified (verified: " + got.n + " names)" : "modified but NOT VERIFIED " + JSON.stringify(got);
        out.results.push(row); continue;
      }
      row.modify_err = String(mod.errmsg).slice(0, 200);
      // 2) create, then delete the old one by its own id
      const c = JSON.parse(JSON.stringify(q));
      strip.forEach(k => { delete c[k]; });
      const cr = await call("createAlert", c);
      if (cr.s !== "ok") { row.action = "FAILED"; row.create_err = String(cr.errmsg).slice(0, 200); out.results.push(row); continue; }
      const newId = cr.r && (cr.r.alert_id || cr.r.id);
      if (!newId) { row.action = "FAILED"; row.create_err = "create returned no alert id - old alert KEPT"; out.results.push(row); continue; }
      const del = await call("deleteAlerts", {alert_ids: [tpl.alert_id]});
      row.action = "created " + newId + (del && del.s === "ok" ? ", old deleted" : ", OLD NOT DELETED (" + JSON.stringify(del).slice(0, 80) + ")");
      out.results.push(row);
    }
    return JSON.stringify(out);
  } catch (e) { out.err = String(e); return JSON.stringify(out); }
})()
"""


def _eval(ws_url: str, expression: str):
    ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": expression, "returnByValue": True,
                                       "awaitPromise": True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return (m.get("result", {}).get("result") or {}).get("value")
    finally:
        ws.close()


def run(dry: bool = False, list_name: str | None = None, upgrade: bool = False) -> int:
    print("Refreshing the S4 GO alerts (75m + 125m -> GM_Swing; positional names are alerted by the Daily board review; board %s)%s - takes ~10-30 s, "
          "the window stays quiet until TradingView answers..." % (
              list_name or todays_list_name(), " [dry run]" if dry else ""), flush=True)
    targets = _chart_targets_all()
    if not targets:
        print("ERROR: no TradingView chart tab over CDP - is TradingView running with the debug port?", flush=True)
        return 2
    cfg = {"listName": list_name or todays_list_name(), "titles": [IN1, IN2, IN3, IN4], "optional": [IN4],
           "resolutions": RESOLUTIONS, "dry": bool(dry), "upgrade": bool(upgrade),
           "planLists": ({} if list_name else {r: todays_list_name(p) for r, p in PLAN_LISTS.items()})}
    js = JS.replace("__CFG__", json.dumps(cfg))
    last = None
    for t in targets:                           # first tab that carries S4
        raw = _eval(t["webSocketDebuggerUrl"], js)
        try:
            res = json.loads(raw) if raw else {"err": "no result"}
        except Exception:
            res = {"err": "unparseable: " + str(raw)[:200]}
        last = res
        if res.get("err", "").startswith("S4 is not on this chart"):
            continue
        break
    res = last or {"err": "no chart tab"}
    for s in res.get("steps", []):
        print("  " + s)
        log.info(s)
    if res.get("err"):
        print("ERROR: " + res["err"])
        log.error(res["err"])
        return 1
    bad = 0
    for r in res.get("results", []):
        if r.get("err") or r.get("action") == "FAILED" or "NOT VERIFIED" in str(r.get("action")):
            bad += 1
        line = "%s: %s" % (r.get("res"), r.get("err") or "%s  %s (%s names) -> %s %s (%s names)  bundle1 %s -> %s chars  bundle2 %s -> %s" % (
            r.get("action"), r["before"]["sym"], r["before"]["n"], r.get("list", ""), r["after"]["sym"], r["after"]["n"],
            r["before"]["b1"], r["after"]["b1"], r["before"]["b2"], r["after"]["b2"]))
        if r.get("note"):
            line += "  [%s]" % r["note"]
        if r.get("modify_err"):
            line += "  (modify refused: %s)" % r["modify_err"]
        if r.get("create_err"):
            line += "  (create failed: %s)" % r["create_err"]
        print("  " + line)
        (log.warning if (r.get("err") or r.get("action") == "FAILED") else log.info)(line)
    print(("DONE - dry run, nothing changed." if dry else "DONE - all alerts refreshed and verified.") if not bad else
          "DONE WITH PROBLEMS - %d alert(s) not refreshed; see above and logs/tv_gm_alerts.log." % bad, flush=True)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="show what would change, touch nothing")
    ap.add_argument("--list", help="watchlist name (default: today's Golden_Matcher_Board-DDMONYY)")
    ap.add_argument("--upgrade-version", action="store_true",
                    help="after an S4 compile: move both alerts to the chart's compiled version when their inputs still exist")
    a = ap.parse_args()
    return run(dry=a.dry_run, list_name=a.list, upgrade=a.upgrade_version)


if __name__ == "__main__":
    sys.exit(main())

"""daily_regime.py - the Daily Regime: what to do, when, and where (7-Oct-2026, Jay).

The ONE source for the Daily Regime manual. It holds every step of the trading week -
before the open, during the session, after the close, and at the weekend - with the page
to open and how to do the step. Three ways to use it:

    python daily_regime.py                  the block for RIGHT NOW (IST, NSE holidays known)
    python daily_regime.py --phase post     one block: pre · session · post · weekend · all
    python daily_regime.py --open           also open that block's pages in the browser
    python daily_regime.py --host jaynuc    links for the phone / another PC (Tailscale)
    python daily_regime.py --build          rewrite Doc 35 (docs/portal/35_daily_regime.html
                                            and docs/35_Daily_Regime.md) from this file

DAILY_REGIME.bat runs the first form. Edit a step HERE and run --build, so the page and
the module never disagree. Times are the Task Scheduler / auto-pilot times on this PC.
Nothing here places an order or changes a setting; it only tells you what to do.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import sys
import webbrowser
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


# ----------------------------------------------------------------------- links ---------
def links(host: str = "localhost") -> dict:
    """Every page the regime opens. Web Commander :8501, the Library :8502 (SERVE_PORTAL)."""
    w = f"http://{host}:8501"
    lib = f"http://{host}:8502/docs/portal"

    def page(p):
        return f"{w}/?p={quote(p)}"
    return {
        "dashboard": (page("DASHBOARD"), "Web Commander · Dashboard"),
        "risk": (page("RISK SHIELD"), "Risk Shield (🔥 Open risk card · 🔁 Swing ↔ Positional tab · warnings)"),
        "portfolio": (page("PORTFOLIO"), "Portfolio"),
        "premarket": (page("PRE-MARKET"), "Pre-Market"),
        "postmarket": (page("POST-MARKET"), "Post-Market"),
        "macro": (page("MACRO"), "Macro (regime, sectors)"),
        "breadth": (page("BREADTH"), "Breadth (McClellan, % above MAs)"),
        "news": (page("NEWS"), "News"),
        "hunter": (page("HUNTER"), "Hunter (fresh Stage-2 breakouts)"),
        "xray": (page("X-RAY"), "X-Ray (fundamentals)"),
        "etf": (page("ETF"), "ETF (screener + rotation)"),
        "journal": (page("JOURNAL"), "Journal"),
        "autopsy": (page("AUTOPSY"), "Autopsy (attribution)"),
        "gm": (f"{w}/?view=gm_window", "Golden Matcher (own window)"),
        "gm_daily": (f"{w}/?view=gm_board_maximized&tf=Daily", "GM board · Daily (positional)"),
        "gm_125": (f"{w}/?view=gm_board_maximized&tf=125m", "GM board · 125m (swing)"),
        "gm_75": (f"{w}/?view=gm_board_maximized&tf=75m", "GM board · 75m (swing)"),
        "library": (f"{lib}/index.html", "The Library"),
        "log": (f"{lib}/31_reviewer_log_v2.html", "Reviewer Log (Doc 31)"),
        "live": (f"{lib}/33_live_record.html", "Live Record (Doc 33)"),
        "tradelog": (f"{lib}/34_trade_log.html", "Trade Log (Doc 34)"),
        "rules": (f"{lib}/25_golden_rules.html", "Golden Rules (Doc 25)"),
        "rules7b": (f"{lib}/25_golden_rules.html#p7b", "Doc 25 Part 7b · swing or positional"),
        "rules7c": (f"{lib}/25_golden_rules.html#p7c", "Doc 25 Part 7c · open-risk budget"),
        "loop": (f"{lib}/26_operating_loop.html", "Operating Loop (Doc 26)"),
        "s4doc": (f"{lib}/22_section_four.html", "Section Four (Doc 22)"),
        "regime_doc": (f"{lib}/35_daily_regime.html", "Daily Regime (Doc 35)"),
        "dhan": ("https://web.dhan.co", "Dhan web (orders · positions · forever orders)"),
    }


# ----------------------------------------------------------------------- steps ---------
# who: "auto" = a scheduled job, nothing to do · "you" = your step.
# links: keys into links(). how: the directions, in order.
PHASES = [
    {"key": "pre", "title": "Before the open", "when": "Trading days · 08:00 – 09:15",
     "lede": "Arrive with the book already decided: stops covered, the day's trims known, and the exposure "
             "rule read. Nothing that happens after 09:15 should be a surprise you could have seen at 08:50.",
     "steps": [
        {"t": "08:00", "who": "auto", "title": "Dhan token check",
         "how": ["Dhan_Token_Check refreshes the API token (TOTP). A failure arrives on Telegram — then run run_token_check.bat."]},
        {"t": "08:30", "who": "auto", "title": "Pre-market brief",
         "how": ["PreMarket_Report sends GIFT Nifty, global cues, F&O participants and the calendar to Telegram."]},
        {"t": "08:45", "who": "auto", "title": "Morning digest",
         "how": ["Morning_Digest: holdings at or below their Chandelier, results within 7 days, the market line."]},
        {"t": "08:45", "who": "you", "title": "Start the desk — MORNING.bat (one click)",
         "how": ["Double-click Morning on the desktop. It starts, in order and only what is not running: TradingView with "
                 "the CDP port, Web Commander, the alert receiver + ngrok, the reviewer banner, the Library server.",
                 "Check the window \"S4 webhook receiver :8000\" is open — closing it is the only way alerts stop being reviewed.",
                 "Check TradingView has its six tabs open: S4 Phase-2 and S5 Layout (yours), S4 Reviewer and S5 Reviewer, "
                 "Phase-1 and Panel Layout. If the reviewer tabs are missing, reviews FAIL loudly; they never borrow yours.",
                 "Banner green = reviewer idle."],
         "links": ["dashboard"]},
        {"t": "08:50", "who": "you", "title": "Read the morning digest, then decide the exits",
         "how": ["Every name listed as at/below its Chandelier: decide now — exit at the open, or hold because the resting "
                 "stop already handles it. Write the decision down; do not decide it in the first minute of trade.",
                 "Results within 3 days on a held name: decide the size (trim or hold), never the direction, from the result risk."]},
        {"t": "08:55", "who": "you", "title": "Risk Shield — stops, open risk, class",
         "how": ["Banners first: 'Stops disagree' or 'Partly covered' → fix on Dhan before 09:15: ONE stop price per holding, "
                 "covering the full quantity, limit price below the trigger.",
                 "🔥 Open risk card: if OVER budget, the expander lists the shares to sell with the stops left in place. "
                 "Those trims are today's first orders (Doc 25 Part 7c).",
                 "🔁 Swing ↔ Positional tab: any EXIT REVIEW name is decided like an exit above."],
         "links": ["risk", "rules7c", "dhan"]},
        {"t": "09:00", "who": "you", "title": "Read the tape and the exposure rule",
         "how": ["Pre-Market page and the MACRO regime. The S4 Section I header (and the SUMMARY's EXPOSURE section) says "
                 "the tier: BEAR or circuit breaker = no new entries today — a management-only day. NEUTRAL = half risk, "
                 "at most 3 new entries a week. A follow-through day or breadth thrust unlocks 2 half-risk pilots.",
                 "This one line decides whether any alert today can become a trade."],
         "links": ["premarket", "macro"]},
     ]},
    {"key": "session", "title": "During market hours", "when": "Trading days · 09:15 – 15:30",
     "lede": "The alerts watch the session, the reviewer reads the chart, and you act only when a review "
             "arrives. No code changes, no compiles, no restarts — if something breaks, roll back, do not fix forward.",
     "steps": [
        {"t": "09:15", "who": "you", "title": "Execute the planned trims and exits first",
         "how": ["The trims and exits you decided before the open, at or shortly after the open. Then resize each "
                 "remaining holding's stop legs to the new quantity (one price, full cover)."],
         "links": ["dhan", "risk"]},
        {"t": "bar closes", "who": "auto", "title": "S4 GO alerts → the reviewer → Telegram",
         "how": ["75m closes 10:30 · 11:45 · 13:00 · 14:15 · 15:30; 125m closes 11:20 · 13:25 · 15:30. The two watchlist "
                 "alerts cover GM_Swing names. About 90 seconds later the review arrives on Telegram and in the Log.",
                 "Daily GO alerts (GM-POS GO, positional names) are reviewed after the close, at 15:31."]},
        {"t": "on a review", "who": "you", "title": "When a review arrives — the execution path",
         "how": ["Open S4 on YOUR S4 Phase-2 tab, on the alert's timeframe. Read the SUMMARY first — EXPOSURE is binding.",
                 "Take only TAKE-IT rulings. A swing name can be timed on 75m/125m; a POSITIONAL name is decided on the "
                 "Daily close only — an intraday GO on a positional name is information, not an entry.",
                 "Size with the Risk Allocator on the S4 stop: 0.5% (stock) / 0.75% (ETF), half in a NEUTRAL tape or on a pilot, "
                 "never above the ₹1L per-trade cap.",
                 "Place the entry and the stop together on Dhan: one stop price, full cover, limit below the trigger.",
                 "Write the class (Swing/Positional) at entry — s4_take does it after the close (below)."],
         "links": ["log", "s4doc", "dhan"]},
        {"t": "any time", "who": "you", "title": "Manual review of a name",
         "how": ["REVIEW.bat SYMBOL TF (e.g. REVIEW TITAN 75) — same path as an alert, on the reviewer's own tabs."]},
        {"t": "all day", "who": "you", "title": "Holdings: let the stops work",
         "how": ["Do not widen a stop unless you cut the quantity so the rupees at risk do not grow (Doc 25 Part 7b).",
                 "Do not convert a swing to positional intraday — conversions are judged on a Daily close.",
                 "A new position's first 10 sessions: the ladder shows 'grace sN/10: held off …' for rungs that were "
                 "true on the entry day. Those describe your entry — act only on the hard exits (stop hit, P&L -8%, Stage 4).",
                 "Optional glance 5 minutes after each bar close; the board is the arm stage and does not decay in 30 minutes."],
         "links": ["rules7b"]},
     ]},
    {"key": "post", "title": "After market hours", "when": "Trading days · 15:30 – 21:00",
     "lede": "The machine rebuilds everything between 16:00 and about 17:30. Your 20 minutes start when the "
             "evening digest lands: read what the day did, then set up tomorrow.",
     "steps": [
        {"t": "15:31", "who": "auto", "title": "Daily GO alerts reviewed",
         "how": ["Positional GM-POS GO alerts that fired on the close are reviewed now — this is the positional entry decision."]},
        {"t": "15:35", "who": "you", "title": "Log the day's decisions",
         "how": ["For each trade taken: python s4_take.py SYMBOL --tf 75 --price FILL --qty SHARES. For each TAKE you passed on: "
                 "python s4_take.py SYMBOL --skip \"why\". This is the scoring — it is the only way the live record can tell you "
                 "whether the system's trades work.",
                 "Check on Dhan that today's entries have their stop resting, full quantity."],
         "links": ["log", "dhan"]},
        {"t": "16:00", "who": "auto", "title": "Exit scan",
         "how": ["Exit_Scan_Daily: stop hits, stage decay, time stops → Telegram ACTION rows."]},
        {"t": "16:30", "who": "auto", "title": "Auto-pilot, journal sync, post-market report",
         "how": ["WeinsteinAutoPilot runs the whole pipeline (scans → Golden Matcher → screens → watchlists → TV sync). "
                 "TradingJournal_DhanSync makes the journal equal the Dhan book and reads the resting stops back. "
                 "PostMarket_Report goes to Telegram. 16:45 Breadth_Daily."]},
        {"t": "~17:00", "who": "auto", "title": "Evening run — boards, bundles, alerts, records",
         "how": ["Phase 12: Daily/125m/75m boards, bundles pushed to S4, the two watchlist alerts moved to today's GM_Swing "
                 "list, positional Daily alerts and zone-approach alerts rebuilt, v67 slots + trail pushed, live record "
                 "and trade log rebuilt, board reviews. Phase 14 sends the evening digest. 17:15 docs truth check, "
                 "18:45 F&O bhavcopy."]},
        {"t": "~17:30", "who": "you", "title": "Read the evening digest",
         "how": ["Phases not OK · boards (5/5 counts against the 20-day median) · reviewer failures · bindings per tab (32/32) · "
                 "alert versions · exit review · TRADE CLASS (positional EXIT REVIEW, swings that may convert).",
                 "Anything red here is fixed tonight — this is the only window for code."]},
        {"t": "17:35", "who": "you", "title": "Risk Shield — the book after today",
         "how": ["🔥 Open risk: over budget → plan tomorrow's trims (they go first at 09:15).",
                 "🔁 Swing ↔ Positional: a swing that passes all four gates may be converted now (it is a Daily close) — "
                 "record it, then on Dhan set the new stop (and sell any trim), then Sync to TV. A losing swing converts only at "
                 "half risk. EXIT REVIEW names are decided for tomorrow's open."],
         "links": ["risk", "rules7b"]},
        {"t": "17:45", "who": "you", "title": "Tomorrow's candidates — the boards",
         "how": ["Daily board: the 5/5 positional names are tomorrow's Daily-close candidates. 125m/75m boards: swing names "
                 "the alerts will time. Open each worth attention in the Golden Matcher and read the decision path.",
                 "ARM what you intend to stalk — an armed name stays in tomorrow's union even if it stops qualifying."],
         "links": ["gm_daily", "gm_125", "gm_75", "gm"]},
        {"t": "18:00", "who": "you", "title": "Read the record",
         "how": ["Reviewer Log: today's rulings. Trade Log: TAKE vs what you bought. Live Record: the system's numbers."],
         "links": ["log", "tradelog", "live"]},
        {"t": "if compiled", "who": "you", "title": "After any S4 / v67 compile",
         "how": ["AFTER_COMPILE.bat — binds and verifies all tabs, pushes the bundles, moves the alerts to the new version, "
                 "restores v67 settings and pushes the slots. All TradingView tabs must be open first."]},
     ]},
    {"key": "weekend", "title": "Weekends and holidays", "when": "Saturday · Sunday · NSE holidays",
     "lede": "The weekly stage only changes after a Friday close. The weekend is for the weekly read, the "
             "book's re-qualification, planning and system work — never for orders.",
     "steps": [
        {"t": "Sat", "who": "you", "title": "Re-qualify the book on the weekly close",
         "how": ["🔁 Swing ↔ Positional: positional holdings that read Stage 3/4 on the confirmed weekly close are EXIT REVIEW — "
                 "plan the exit for Monday. WATCH names (below the 200-DMA, weekly trend down): decide trim or hold.",
                 "🔥 Open risk: the budget for Monday's tier; plan the trims."],
         "links": ["risk", "rules7b", "rules7c"]},
        {"t": "Sat", "who": "you", "title": "The market's stage before the stock's",
         "how": ["MACRO and BREADTH: regime score, % of stocks above the 50/200-DMA, new highs vs lows, Stage-2 share, "
                 "McClellan. Write one line: what tier Monday is likely to start in, and what would unlock pilots.",
                 "Sector rotation: the RRG (START_RRG_STUDIO.bat — it uses :8502, so stop the Library server first)."],
         "links": ["macro", "breadth"]},
        {"t": "Sat", "who": "you", "title": "Strategic planning — fresh Stage-2 names",
         "how": ["HUNTER and the Golden Matcher Daily board: Hunter / EarlyBird picks, fresh Stage-2 breakouts. Weekly charts "
                 "on TradingView for the GM_Positional list; mark Daily+ demand zones by hand where the engine has none.",
                 "X-Ray for the fundamentals of anything you would stalk. ETF page for the rotation read."],
         "links": ["hunter", "gm_daily", "xray", "etf"]},
        {"t": "Sun", "who": "you", "title": "Review the week",
         "how": ["Trade Log and Live Record: what was taken, skipped, and how the system's trades did. Journal: lessons on "
                 "every exit. logs/board_counts_history.csv: were quiet days the market or a gate?",
                 "Monthly: AUTOPSY → Attribution."],
         "links": ["tradelog", "live", "journal", "autopsy"]},
        {"t": "Sun 19:00", "who": "auto", "title": "Weekly report",
         "how": ["Weekly_Report goes to Telegram."]},
        {"t": "any time", "who": "you", "title": "System work",
         "how": ["Code changes, compiles and restarts belong here or after 15:30. After an S4 / v67 compile: AFTER_COMPILE.bat. "
                 "Before Monday: Web Commander restarted on the latest code, and MORNING.bat on Monday morning."],
         "links": ["library"]},
     ]},
]


# ----------------------------------------------------------------------- phase now -----
def phase_now(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(IST)
    d = now.date()
    try:
        import nse_calendar as nc
        trading = nc.is_trading_day(d)
    except Exception:
        trading = d.weekday() < 5
    if not trading:
        return "weekend"
    hm = (now.hour, now.minute)
    if hm < (9, 15):
        return "pre"
    if hm < (15, 30):
        return "session"
    return "post"


def _exposure_line() -> str:
    try:
        import house_policy as hp
        return hp.exposure_status().get("text", "")
    except Exception as e:
        return f"(exposure rule unreadable: {e})"


# ----------------------------------------------------------------------- CLI -----------
def render_text(keys: list[str], host: str) -> str:
    L = links(host)
    out = []
    for ph in PHASES:
        if ph["key"] not in keys:
            continue
        out += ["", "=" * 78, f"{ph['title'].upper()}  ·  {ph['when']}", "=" * 78, ph["lede"], ""]
        for s in ph["steps"]:
            tag = "AUTO" if s["who"] == "auto" else "YOU "
            out.append(f"[{tag}] {s['t']:<11} {s['title']}")
            for h in s["how"]:
                out.append("        - " + h)
            for k in s.get("links", []):
                out.append(f"        > {L[k][1]}: {L[k][0]}")
            out.append("")
    return "\n".join(out)


def open_links(keys: list[str], host: str) -> int:
    L, seen, n = links(host), set(), 0
    for ph in PHASES:
        if ph["key"] in keys:
            for s in ph["steps"]:
                for k in s.get("links", []):
                    if k not in seen:
                        seen.add(k)
                        webbrowser.open_new_tab(L[k][0])
                        n += 1
    return n


# ----------------------------------------------------------------------- the manual ----
def _css() -> str:
    """The Library's look: the <head> + <style> of Doc 26, so every page reads the same."""
    p = os.path.join(HERE, "docs", "portal", "26_operating_loop.html")
    try:
        s = open(p, encoding="utf-8").read()
        return s[: s.index("</style>") + len("</style>")].replace(
            "<title>GM + S4 Operating Loop</title>", "<title>Daily Regime</title>")
    except Exception:
        return '<meta charset="utf-8">\n<title>Daily Regime</title>'


def build_html(host: str = "localhost") -> str:
    L = links(host)
    e = html.escape
    parts = [_css(), """
<style>
.lk{margin:8px 0 0;display:flex;flex-wrap:wrap;gap:8px}
.lk a{font-family:var(--mono);font-size:12px;text-decoration:none;color:var(--go);border:1px solid var(--go-rule);
  background:var(--surface);border-radius:3px;padding:2px 8px}
.lk a:hover{background:var(--go-bg)}
ul.how{margin:6px 0 0;padding-left:18px}
ul.how li{font-size:15px;color:var(--ink-2);margin:0 0 5px;max-width:64ch}
.toc{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 0}
.toc a{font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);
  text-decoration:none;border:1px solid var(--rule);padding:6px 10px;background:var(--surface)}
</style>
<header class="mast"><div class="mast-in">
  <p class="eyebrow">Doc 35 · Process · 7 Oct 2026</p>
  <h1>Daily Regime</h1>
  <p class="dek">What to do on a trading day — <b>before the open, during the session, after the close</b> —
  and at the weekend, with the page to open for each step. The green steps are yours; the rest run by themselves.
  The book's safety comes first every morning: stops covered, open risk inside budget, the exposure rule read.</p>
  <div class="toc">""" + "".join(f'<a href="#{p["key"]}">{e(p["title"])}</a>' for p in PHASES) + """</div>
</div></header>
<div class="wrap"><main>
<section>
  <p class="pt">How to use it</p>
  <h2>One command, the right block</h2>
  <p>Run <span class="m">DAILY_REGIME.bat</span> &mdash; the Desktop shortcut <b>Daily Regime</b> (calendar icon) &mdash; (or <span class="m">python daily_regime.py</span>) and it prints the block for
  right now — it knows IST and the NSE holidays — with every link. <span class="m">--open</span> also opens those pages;
  <span class="m">--phase post</span> picks a block; <span class="m">--host jaynuc</span> gives links for the phone. This page is
  generated from the same file (<span class="m">daily_regime.py --build</span>), so the two never disagree.</p>
  <div class="note"><span class="lbl">The three numbers that decide every day</span>
  <p><b>Exposure tier</b> (S4 Section I header / SUMMARY EXPOSURE): whether you may enter at all, and at what risk.
  <b>Open risk vs budget</b> (Risk Shield 🔥 card): 6% of capital in an OPEN tape, 3% in NEUTRAL or BEAR.
  <b>Stops</b>: one price per holding, full quantity, limit below the trigger.</p></div>
</section>
"""]
    for ph in PHASES:
        parts.append(f'<section id="{ph["key"]}">\n  <p class="pt">{e(ph["when"])}</p>\n  <h2>{e(ph["title"])}</h2>\n'
                     f'  <p class="lede">{e(ph["lede"])}</p>\n  <div class="tl">')
        for s in ph["steps"]:
            you = s["who"] == "you"
            who = "you" if you else "automatic"
            lis = "".join(f"<li>{e(h)}</li>" for h in s["how"])
            lk = "".join(f'<a href="{e(L[k][0])}">{e(L[k][1])}</a>' for k in s.get("links", []))
            parts.append(
                f'\n    <div class="ev{" you" if you else ""}">\n      <div class="clk">{e(s["t"])}</div>\n'
                f'      <div class="bd">\n        <p class="t">{e(s["title"])}<span class="who">{who}</span></p>\n'
                f'        <ul class="how">{lis}</ul>' + (f'\n        <div class="lk">{lk}</div>' if lk else "")
                + "\n      </div>\n    </div>")
        parts.append("\n  </div>\n</section>\n")
    parts.append("""<section>
  <p class="pt">Related</p>
  <h2>Where the rules behind each step live</h2>
  <p>Doc 25 Golden Rules — Part 7b (swing or positional) and Part 7c (the open-risk budget) · Doc 26 Operating Loop ·
  Doc 22 Section Four · Doc 32 The Reviewer · Doc 31 / 33 / 34 for the record.</p>
</section>
<footer><em>Generated from daily_regime.py.</em> Change a step there and run <span class="m">--build</span>.</footer>
</main></div>
""")
    return "".join(parts)


def build_md(host: str = "localhost") -> str:
    L = links(host)
    o = ["# DAILY REGIME — what to do, when, and where (Doc 35)", "",
         "*Generated from `daily_regime.py` — edit the steps there and run `python daily_regime.py --build`.*", "",
         "Run `DAILY_REGIME.bat` (or `python daily_regime.py`) for the block that applies right now, with links. "
         "`--open` opens the pages, `--phase pre|session|post|weekend|all` picks a block, `--host jaynuc` gives phone links.",
         "", "**The three numbers that decide every day:** the exposure tier (whether you may enter, and at what risk), "
         "open risk against its budget (6% OPEN, 3% NEUTRAL or BEAR), and the stops (one price, full cover, limit below "
         "the trigger).", ""]
    for ph in PHASES:
        o += ["---", "", f"## {ph['title'].upper()} — {ph['when']}", "", ph["lede"], ""]
        for s in ph["steps"]:
            o.append(f"### {s['t']} · {s['title']} ({'YOU' if s['who'] == 'you' else 'automatic'})")
            o += [f"- {h}" for h in s["how"]]
            if s.get("links"):
                o.append("- Open: " + " · ".join(f"[{L[k][1]}]({L[k][0]})" for k in s["links"]))
            o.append("")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=["pre", "session", "post", "weekend", "all"])
    ap.add_argument("--open", action="store_true", help="open the block's pages in the browser")
    ap.add_argument("--host", default="localhost", help="localhost (this PC) or jaynuc (phone / other PC)")
    ap.add_argument("--build", action="store_true", help="rewrite Doc 35 (html + md) from this file")
    a = ap.parse_args(argv)
    if a.build:
        with open(os.path.join(HERE, "docs", "portal", "35_daily_regime.html"), "w", encoding="utf-8") as f:
            f.write(build_html())
        with open(os.path.join(HERE, "docs", "35_Daily_Regime.md"), "w", encoding="utf-8") as f:
            f.write(build_md())
        print("built docs/portal/35_daily_regime.html and docs/35_Daily_Regime.md")
        return 0
    now = dt.datetime.now(IST)
    ph = a.phase or phase_now(now)
    keys = [p["key"] for p in PHASES] if ph == "all" else [ph]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"DAILY REGIME · {now:%a %d %b %Y %H:%M} IST · block: {ph}")
    ex = _exposure_line()
    if ex:
        print("EXPOSURE: " + ex)
    print(render_text(keys, a.host))
    print(f"Full manual: {links(a.host)['regime_doc'][0]}")
    if a.open:
        print(f"opened {open_links(keys, a.host)} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Pre-launch check: undefined names in the surfaces Jay actually trades from.

WHY THIS EXISTS (11-Aug-2026)
-----------------------------
Two Risk Shield faults on the same night were the same bug: a name referenced
inside a per-symbol loop that is only DEFINED further down the file. Python
does not complain until that line runs, and both sites sat inside a batch
`except` that reported the crash as "Technicals fetch failed this run" — a DATA
problem. So a code fault masqueraded as a flaky feed for an entire session.

`py_compile` cannot catch this: undefined names are legal at compile time.
`pyflakes` catches it in about a second, without importing or executing
anything. That is the whole point — it is a parse, so it is safe to run on a
Streamlit app at launch.

Scope is deliberately narrow: the app plus the modules on the Golden Matcher /
Risk Shield / screener paths. Peripheral scripts have their own known
undefined names (traceback/os imports missing in market_monitor_agent,
quant_analyst, visual_manager, tradingview_automation_v2) and flagging those
every launch would make this wallpaper. Add a file here when it joins a live
path, not before.

Exit codes: 0 = clean, 1 = undefined names found, 2 = could not run (pyflakes
missing / a file unreadable). The launcher treats 2 as "carry on" — a missing
linter must never stop Jay from opening the board.

UNATTENDED MODE (`--unattended`)
--------------------------------
For Task Scheduler jobs and the auto-pilot, where nobody is watching a console.
Findings go to logs/preflight.log and to Telegram, and the exit code is ALWAYS
0 so the job proceeds. That is deliberate: a linter must never be the reason
the stop-trail job skips a day. The point of running it here is that a fault in
gtt_auto_shield or journal_sync shows up as a message rather than as a job that
appears to have run fine — the exact failure mode of the 24-Jul trail outage.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys

# Files on a live trading path. Order = roughly the order a fault would bite.
WATCHED = [
    "weinstein_commander_web_v4.0.py",
    "gm_trigger_board.py",
    "risk_common.py",
    "pyramid_logic.py",
    "bull_screener.py",
    "recovery_screener.py",
    "zone_engine.py",
    "pa_patterns.py",
    "strict_trend.py",
    "gm_armed.py",
    # Unattended path — these run with nobody watching, which is exactly where
    # a silent fault survives longest (the trail job went dark for three weeks).
    "journal_sync.py",
    "gtt_auto_shield.py",
    "run_pipeline.py",
    "pre_trade_gate.py",
    "scheduler_daemon.py",
]


def _report_unattended(root: str, hits: list[str]) -> None:
    """Log + Telegram. Never raises — a reporting failure must not fail a job."""
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        logs = os.path.join(root, "logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, "preflight.log"), "a", encoding="utf-8") as fh:
            fh.write(f"---------- {stamp} ----------\n")
            for h in hits:
                fh.write(f"  {h}\n")
    except Exception:
        pass

    try:
        sys.path.insert(0, root)
        from scheduler_daemon import send_telegram
        body = "\n".join(hits[:10])
        more = f"\n… and {len(hits) - 10} more" if len(hits) > 10 else ""
        send_telegram(
            "⚠️ <b>Preflight: undefined names</b>\n"
            f"<pre>{body}{more}</pre>\n"
            "These crash on the line that reaches them. A batch except will "
            "report it as a data failure — check before trusting today's run."
        )
    except Exception:
        pass


def main() -> int:
    unattended = "--unattended" in sys.argv
    root = os.path.dirname(os.path.abspath(__file__))

    try:
        from pyflakes.api import check
        from pyflakes.reporter import Reporter
        from pyflakes import messages as pf_messages
    except Exception as exc:  # linter absent — never block the launch
        print(f"  [preflight] pyflakes unavailable ({exc}) - skipping check")
        return 0 if unattended else 2

    # Keep ONLY the undefined-name family. Unused imports and shadowed names
    # are style; an undefined name is a guaranteed runtime crash on the line
    # that reaches it, which is exactly the class this exists to catch.
    keep = (
        pf_messages.UndefinedName,
        pf_messages.UndefinedLocal,
        pf_messages.UndefinedExport,
    )

    class _Collect(Reporter):
        def __init__(self):
            super().__init__(sys.stdout, sys.stdout)
            self.hits: list[str] = []

        def flake(self, message):
            if isinstance(message, keep):
                self.hits.append(str(message))

        def unexpectedError(self, filename, msg):
            self.hits.append(f"{filename}: could not parse: {msg}")

        def syntaxError(self, filename, msg, lineno, offset, text):
            self.hits.append(f"{filename}:{lineno}: syntax error: {msg}")

    rep = _Collect()
    scanned = 0
    for name in WATCHED:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
        except Exception as exc:
            print(f"  [preflight] could not read {name}: {exc}")
            return 0 if unattended else 2
        check(src, name, rep)
        scanned += 1

    if rep.hits and unattended:
        # NEVER exit non-zero here: the job must still run. The finding is a
        # message, not a gate.
        for h in rep.hits:
            print(f"  [preflight] UNDEFINED NAME: {h}")
        _report_unattended(root, rep.hits)
        return 0

    if rep.hits:
        print()
        print("  " + "=" * 68)
        print("  [preflight] UNDEFINED NAMES - these crash the moment that line runs.")
        print("  " + "=" * 68)
        for h in rep.hits:
            print(f"    {h}")
        print()
        print("  A name like this inside a try/except reads as a DATA failure in the")
        print("  UI, so it can hide for a whole session. Fix before trusting the page.")
        print()
        return 1

    print(f"  [preflight] {scanned} live-path modules clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

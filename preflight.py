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
"""

from __future__ import annotations

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
    "journal_sync.py",
    "scheduler_daemon.py",
]


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))

    try:
        from pyflakes.api import check
        from pyflakes.reporter import Reporter
        from pyflakes import messages as pf_messages
    except Exception as exc:  # linter absent — never block the launch
        print(f"  [preflight] pyflakes unavailable ({exc}) - skipping check")
        return 2

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
            return 2
        check(src, name, rep)
        scanned += 1

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

"""Parity guard — a Python change to a shared signal must travel with its Pine side.

Why (20-Sep audit, finding PAR-01): commit 3ae3d72b changed Bull Engulf and Stage-2
Launch in pa_patterns.py and never reached S4Core / v67. Nothing mechanical kept the
surfaces equal, so the drift sat in production for six weeks.

Rule: a commit whose STAGED diff touches a parity-critical Python definition must also
stage S4Core.pine or the v67 dashboard, OR carry "PARITY-WAIVER: <reason>" in its
message (a genuine Python-only change: a comment, a test, a refactor that moves no
number). The waiver is the point — it makes the decision visible in `git log`.

Called by tools/hooks/commit-msg with the message file path. Exit 1 blocks the commit.
"""
from __future__ import annotations

import re
import subprocess
import sys

# whole files: any change is a signal change
CRITICAL_FILES = ("pa_patterns.py", "strict_trend.py")
# (file, pattern) — only hunks that touch these definitions count
CRITICAL_DEFS = (
    ("bull_screener.py", re.compile(r"compute_weekly_stage_and_wks|_drop_forming_week")),
    ("rrg_engine.py", re.compile(r"STRIKE_CAL")),
)
PINE_SIDE = re.compile(r"(^|/)S4Core\.pine$|(^|/)Weinstein and Swing Pro Dashboard.*\.pine$")
WAIVER = "PARITY-WAIVER:"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def critical_hits(staged: list[str], diff_of) -> list[str]:
    """Names of the parity-critical things the staged diff touches."""
    hits = [f for f in staged if f.rsplit("/", 1)[-1] in CRITICAL_FILES]
    for fname, pat in CRITICAL_DEFS:
        for f in staged:
            if f.rsplit("/", 1)[-1] != fname:
                continue
            # -U0 hunks: the @@ header names the enclosing def; +/- lines are the change
            for line in diff_of(f).splitlines():
                if (line.startswith("@@") or line[:1] in "+-") and not line.startswith(("+++", "---")):
                    if pat.search(line):
                        hits.append(f"{fname}: {pat.pattern}")
                        break
    return hits


def check(msg: str, staged: list[str], diff_of) -> str | None:
    """None when the commit may proceed, else the reason it is blocked."""
    hits = critical_hits(staged, diff_of)
    if not hits or WAIVER in msg or any(PINE_SIDE.search(f) for f in staged):
        return None
    return ("PARITY GUARD: this commit changes parity-critical Python\n  - "
            + "\n  - ".join(hits)
            + "\nbut stages no S4Core.pine / v67 dashboard change.\n"
            "Either stage the matching Pine change, or add a line\n"
            f"  {WAIVER} <why this cannot move a signal>\n"
            "to the commit message.")


def main(msg_path: str) -> int:
    msg = open(msg_path, encoding="utf-8", errors="replace").read()
    staged = [s for s in _git("diff", "--cached", "--name-only").splitlines() if s]
    why = check(msg, staged, lambda f: _git("diff", "--cached", "-U0", "--", f))
    if why:
        sys.stderr.write(why + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

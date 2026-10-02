"""board_reviews.py - review every 5/5 GO on the three GM boards, labelled "board" (2-Oct-2026).

Jay's evening routine after the auto-pilot was: read the 5/5 rows on the Daily, 125m and 75m
boards and run REVIEW.bat on each - so those reviews landed in the Log as "manual". This
does it as auto-pilot Phase 13 and labels them "board", so the Reviewer Log separates:
    s4-alert   S4's own GO alert fired in the session
    board      a 5/5 GO on an evening board (this script)
    manual     anything asked for by hand with REVIEW.bat

Route: the names are POSTed to the local alert receiver (:8000) tagged "- board", exactly as
REVIEW.bat does, so they queue behind any other review, use the reviewer's own tabs, show on
the banner, go to Telegram and land in the Log. If the receiver is not running, the reviewer
runs directly (s4_review.py --board <tf>), which labels them "board" too.

    python board_reviews.py            queue every board's 5/5 GO
    python board_reviews.py --dry-run  list them, queue nothing
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARDS = (("daily", "D"), ("125m", "125"), ("75m", "75"))


def five_of_five(board: str) -> list[str]:
    import s4_review as sr
    try:
        return sr.board_symbols(board, live=False)        # "N/N GO" rows only
    except SystemExit as e:                               # no cache for that board
        print("  %s: %s" % (board, e))
        return []


def main() -> int:
    dry = "--dry-run" in sys.argv
    pairs = []
    for board, tf in BOARDS:
        syms = five_of_five(board)
        print("  %-5s %2d at 5/5 GO: %s" % (board, len(syms), ", ".join(syms) or "-"))
        pairs += [(s, tf) for s in syms]
    if not pairs:
        print("board reviews: nothing at 5/5 GO on any board")
        return 0
    if dry:
        print("board reviews: %d (dry run, nothing queued)" % len(pairs))
        return 0
    import review_many as rm
    if rm.receiver_up():
        bad = rm.post(pairs, tag="board")
        print("board reviews: %d queued on the receiver (one at a time, ~90 s each)%s"
              % (len(pairs) - bad, ("; %d failed" % bad) if bad else ""))
        return 1 if bad else 0
    print("receiver not running - reviewing directly (labelled board)")
    py = sys.executable
    rc = 0
    for board, _tf in BOARDS:
        if five_of_five(board):
            r = subprocess.run([py, os.path.join(HERE, "s4_review.py"), "--board", board], cwd=HERE)
            rc |= r.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())

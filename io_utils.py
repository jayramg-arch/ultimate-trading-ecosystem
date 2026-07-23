# io_utils.py — tiny shared I/O primitives (no heavy deps, import-safe everywhere).
#
# atomic_write_text was defined inside gm_trigger_board.py; it is hoisted here so
# other writers (the matcher's FINAL_*.csv, MASTER_Golden_Picks.csv, the catalyst
# history) can share ONE atomic-write primitive instead of each risking a torn file
# on a crash mid-write. gm_trigger_board re-exports it for back-compat.

import os


def atomic_write_text(path: str, text: str) -> None:
    """Write-tmp-then-os.replace so a kill mid-write can never leave a truncated
    file (a half-written CSV/JSON used to silently read back as EMPTY — curated
    state lost). os.replace is atomic on the same volume on Windows + POSIX."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)

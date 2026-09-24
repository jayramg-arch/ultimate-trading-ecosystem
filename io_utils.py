# io_utils.py — tiny shared I/O primitives (no heavy deps, import-safe everywhere).
#
# atomic_write_text was defined inside gm_trigger_board.py; it is hoisted here so
# other writers (the matcher's FINAL_*.csv, MASTER_Golden_Picks.csv, the catalyst
# history) can share ONE atomic-write primitive instead of each risking a torn file
# on a crash mid-write. gm_trigger_board re-exports it for back-compat.

import os
import random
import threading
import time


def atomic_write_text(path: str, text: str, *, retries: int = 5) -> None:
    """Write-tmp-then-os.replace so a kill mid-write can never leave a truncated
    file (a half-written CSV/JSON used to silently read back as EMPTY — curated
    state lost). os.replace is atomic on the same volume on Windows + POSIX.

    THE TEMP NAME IS UNIQUE PER WRITER (24-Sep-2026). It used to be `path + ".tmp"`,
    a single fixed name shared by every caller, which made this atomic against a
    CRASH but not against CONCURRENCY:

        writer A  open(tmp,"w") ......... writing .........  os.replace(tmp, path)
        writer B        open(tmp,"w")  <-- truncates A's temp file under it
                                          os.replace(tmp, path)  <-- one of them
                                                                     raises

    Reproduced on Windows with two threads writing different-length documents to one
    path: `PermissionError: [WinError 5] Access is denied: '<path>.tmp' -> '<path>'`,
    because the other writer still holds the temp file open. The write is then LOST —
    and a caller that wraps the save in a try/except records nothing. There are 27
    matching hits in logs/gm_errors.log, and the armed register's mtime sat unchanged
    for eleven days while the UI believed it was saving.

    The Web Commander is the natural trigger: Streamlit reruns, fragments and the
    bar-close refresh can have two script runs alive at once, and both save the same
    register.

    pid + thread id + a counter + 4 random hex: unique across processes, threads and
    two calls in the same millisecond. The retry covers the remaining Windows case
    where an antivirus or an indexer briefly holds the destination.
    """
    tmp = "%s.%d.%d.%s.tmp" % (path, os.getpid(), threading.get_ident(),
                               "%04x" % random.getrandbits(16))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    last = None
    for attempt in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:          # Windows: destination briefly locked
            last = e
            time.sleep(0.05 * (attempt + 1))
    # Never leave our temp file behind to be mistaken for real state.
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise last

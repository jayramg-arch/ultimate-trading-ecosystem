"""commander_pages - one file per Web Commander page (25-Sep-2026, split phase 3).

The app calls run(slug, globals()) in place of each `if/elif page == ...` body, so a page
executes in the app's own namespace exactly as it did inline: same globals, same widget
keys, same st.stop(). What changes is where the code LIVES - one page per file, tracebacks
that name the page, and a page edit that cannot break another page's syntax.

Compiled code is cached per file and re-used until the file's mtime changes. Note that
Streamlit's file watcher does not see these files: after editing a page, restart Web
Commander (STOP_COMMANDER.bat -> relaunch), as for any other change.
"""
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_CODE = {}


def path(slug: str) -> str:
    return os.path.join(_DIR, slug + ".py")


def run(slug: str, g: dict) -> None:
    p = path(slug)
    mt = os.path.getmtime(p)
    hit = _CODE.get(p)
    if hit is None or hit[0] != mt:
        with open(p, encoding="utf-8") as f:
            hit = (mt, compile(f.read(), p, "exec"))
        _CODE[p] = hit
    exec(hit[1], g)

"""Test isolation that cannot be forgotten.

WHY THIS EXISTS (10-Aug-2026). `gm_armed._STORE` is a module-level path pointing at the
LIVE register, `gm_armed.json`. Two test files redirect it to a temp file in a helper —
but only when the helper is called, and 16 of 30 tests never called it. Those tests wrote
straight into production.

It was not theoretical. Running the suite today put records literally named `OLD` and `X`
into the live register, and `logs/gm_errors.log` shows the board expiring them:

    16:00:37 INFO    gm_armed: expired 1 stale record(s): OLD
    16:00:37 INFO    gm_armed: expired 1 stale record(s): X
    16:00:38 WARNING gm_armed: store unreadable — register treated as empty: ...

The WARNING is the second half of the same problem: a test writing the file while a board
tab read it produced a torn read. The file was never actually corrupt — `json.load` on it
succeeds — which is why chasing it as "corrupt JSON" (an open item since 3-Aug) went
nowhere. Concurrency, not corruption.

The fix is autouse and session-wide rather than per-test opt-in, because the failure mode
is a test AUTHOR forgetting, and a guard you must remember is not a guard. Individual tests
may still point `_STORE` wherever they like — this only guarantees the DEFAULT is never
production.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _isolate_armed_register(tmp_path, monkeypatch):
    """Point every state store that defaults to a repo file at a per-test temp file.

    monkeypatch restores the original after each test, so an import-order quirk cannot
    leave a redirect dangling into the next file — the mechanism that let one file's
    `importlib.reload` reset another file's redirect back to production.
    """
    try:
        import gm_armed
    except Exception:                       # module not importable in this environment
        return
    monkeypatch.setattr(gm_armed, "_STORE", str(tmp_path / "gm_armed.json"), raising=False)


@pytest.fixture(autouse=True)
def _guard_production_state(monkeypatch):
    """Belt and braces: if a test somehow still resolves a production state file, fail
    loudly instead of writing it. Only the files that hold LIVE trading state are listed —
    caches and generated CSVs are regenerable and not worth the friction."""
    protected = {"gm_armed.json", "gm_settings.json", "gm_rrg_flags.json",
                 "trade_journal_v6.db"}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _is_live(path) -> bool:
        try:
            p = os.path.abspath(str(path))
            return os.path.dirname(p) == root and os.path.basename(p) in protected
        except Exception:
            return False                    # never let the guard itself break a test

    def _boom(path):
        raise AssertionError(
            f"test tried to WRITE live state: {os.path.basename(str(path))}. "
            f"Redirect the module's store to tmp_path instead.")

    real_open, real_replace, real_rename = open, os.replace, os.rename

    def guarded_open(file, mode="r", *a, **kw):
        if any(w in mode for w in ("w", "a", "+")) and _is_live(file):
            _boom(file)
        return real_open(file, mode, *a, **kw)

    # os.replace / os.rename are the ones that actually mattered. The first version of
    # this guard only wrapped open() and checked the basename — and it did NOT fire,
    # because the writers here go through io_utils.atomic_write_text, which writes a
    # `.tmp` file (a name the basename check misses) and then os.replace()s it into
    # position without ever open()ing the real path. A probe test proved it by writing
    # the live register the guard was supposed to protect. Guard the DESTINATION.
    def guarded_replace(src, dst, *a, **kw):
        if _is_live(dst):
            _boom(dst)
        return real_replace(src, dst, *a, **kw)

    def guarded_rename(src, dst, *a, **kw):
        if _is_live(dst):
            _boom(dst)
        return real_rename(src, dst, *a, **kw)

    monkeypatch.setattr("builtins.open", guarded_open)
    monkeypatch.setattr(os, "replace", guarded_replace)
    monkeypatch.setattr(os, "rename", guarded_rename)

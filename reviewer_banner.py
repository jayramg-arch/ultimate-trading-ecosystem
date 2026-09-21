"""Reviewer banner — a small always-on-top strip that says whether the AI reviewer
is driving your TradingView charts right now.

21-Sep-2026. STANDALONE and READ-ONLY: it tails `logs/s4_alert_review.log` and
touches nothing else — no imports from the receiver, no CDP, no writes except its
own saved position. Start it, stop it, or kill it at any time; the reviewer neither
knows nor cares. (After the close this same state will be driven from `_run()`
directly, which removes the log-parsing guesswork; until then this is exact enough,
because the worker is serial — one review at a time.)

    python reviewer_banner.py            (or REVIEWER_BANNER.bat)

READING IT
    red     the reviewer HAS your charts — symbol, TF, elapsed, and how many are
            queued behind it. Your chart will be put back when it finishes.
    amber   review done, chart being restored (a second or two).
    green   idle. Shows the last name it read and how long that took.

Drag it anywhere with the left button; the position is remembered. Right-click to
close. It never steals focus.
"""
from __future__ import annotations

import json
import os
import re
import time
import tkinter as tk
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs", "s4_alert_review.log")
POS = os.path.join(HERE, "logs", "reviewer_banner_pos.json")
STATUS = os.path.join(HERE, "logs", "reviewer_status.json")   # written by s4_alert_review._run
STATUS_MAX_AGE_S = 6 * 3600   # older than this = a stale file from a receiver that has since died

POLL_MS = 1000
TS = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"

RE_QUEUED = re.compile(TS + r"\s+queued (\S+) (\S+) from")
RE_DONE = re.compile(TS + r"\s+(\S+) (\S+) reviewed in (\d+)s")
RE_FAIL = re.compile(TS + r"\s+(\S+) (\S+) (?:FAILED|review rc)")
RE_RESTORED = re.compile(TS + r"\s+chart restore(?:d|d failed| failed)")

C_BUSY, C_WAIT, C_IDLE, C_DEAD = "#7F1D1D", "#78350F", "#14532D", "#1F2937"
FG = "#F8FAFC"


def _parse(line: str):
    """-> (kind, ts, symbol, tf, secs) for the events that change state."""
    m = RE_QUEUED.match(line)
    if m:
        return ("queued", m.group(1), m.group(2), m.group(3), None)
    m = RE_DONE.match(line)
    if m:
        return ("done", m.group(1), m.group(2), m.group(3), int(m.group(4)))
    m = RE_FAIL.match(line)
    if m:
        return ("failed", m.group(1), m.group(2), m.group(3), None)
    if RE_RESTORED.match(line):
        return ("restored", RE_RESTORED.match(line).group(1), None, None, None)
    return None


class Banner:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=C_IDLE)

        self.label = tk.Label(self.root, text="reviewer · starting…", bg=C_IDLE, fg=FG,
                              font=("Consolas", 10, "bold"), padx=12, pady=6, anchor="w")
        self.label.pack(fill="both", expand=True)

        x, y = self._load_pos()
        self.root.geometry("+%d+%d" % (x, y))

        for w in (self.root, self.label):
            w.bind("<Button-1>", self._grab)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", lambda e: self._save_pos())
            w.bind("<Button-3>", lambda e: self.root.destroy())

        # log tail state
        self._pos = 0
        self._size = -1
        # review state
        self.pending: list[tuple[str, str]] = []   # queued, not yet terminal
        self.current: tuple[str, str, datetime] | None = None
        self.restoring = False
        self.last: str = ""

        self._prime()
        self._tick()

    # ── window helpers ────────────────────────────────────────────────────
    def _load_pos(self) -> tuple[int, int]:
        try:
            with open(POS, encoding="utf-8") as f:
                d = json.load(f)
            return int(d["x"]), int(d["y"])
        except Exception:
            return self.root.winfo_screenwidth() - 430, 12

    def _save_pos(self) -> None:
        try:
            os.makedirs(os.path.dirname(POS), exist_ok=True)
            with open(POS, "w", encoding="utf-8") as f:
                json.dump({"x": self.root.winfo_x(), "y": self.root.winfo_y()}, f)
        except Exception:
            pass

    def _grab(self, e) -> None:
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag(self, e) -> None:
        self.root.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    # ── log tail ──────────────────────────────────────────────────────────
    def _prime(self) -> None:
        """Replay today's lines once so a banner started mid-review shows the truth."""
        try:
            self._size = os.path.getsize(LOG)
            with open(LOG, encoding="utf-8", errors="replace") as f:
                today = datetime.now().strftime("%Y-%m-%d")
                for line in f:
                    if line.startswith(today):
                        self._apply(line)
                self._pos = f.tell()
        except Exception:
            self._pos, self._size = 0, -1

    def _read_new(self) -> None:
        try:
            size = os.path.getsize(LOG)
        except OSError:
            return
        if size < self._size:          # rotated or truncated — start over
            self._pos = 0
            self.pending, self.current, self.restoring = [], None, False
        self._size = size
        if size == self._pos:
            return
        try:
            with open(LOG, encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                for line in f:
                    self._apply(line)
                self._pos = f.tell()
        except Exception:
            pass

    def _apply(self, line: str) -> None:
        ev = _parse(line)
        if not ev:
            return
        kind, ts, sym, tf, secs = ev
        when = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        if kind == "queued":
            self.pending.append((sym, tf))
        elif kind in ("done", "failed"):
            self.pending = [p for p in self.pending if p != (sym, tf)]
            self.current = None
            self.restoring = True
            self.last = ("%s %sm · %ds" % (sym, tf, secs)) if secs is not None \
                else ("%s %sm · failed" % (sym, tf))
        elif kind == "restored":
            self.restoring = False
        # the worker is serial: the oldest still-pending item is the one running
        if self.pending and self.current is None:
            sym, tf = self.pending[0]
            self.current = (sym, tf, when)

    # ── paint ─────────────────────────────────────────────────────────────
    def _from_status(self):
        """(text, bg) from the receiver's own status file, or None to fall back to the log.
        21-Sep evening: _run() writes busy / restoring / idle at each transition, so this
        is exact; the log tail below is only for a receiver that predates it."""
        try:
            if time.time() - os.path.getmtime(STATUS) > STATUS_MAX_AGE_S:
                return None
            with open(STATUS, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return None
        st, sym, tf = d.get("state"), d.get("symbol", ""), d.get("tf", "")
        pend = int(d.get("pending") or 0)
        if st == "busy":
            el = max(0, int(time.time() - float(d.get("started") or time.time())))
            return ("● REVIEWER HAS THE CHARTS · %s %sm · %ds%s" % (
                sym, tf, el, ("  +%d queued" % pend) if pend else ""), C_BUSY)
        if st == "restoring":
            return ("◐ %s done · restoring your chart…" % sym, C_WAIT)
        if st == "idle":
            last = d.get("last") or ""
            return ("○ reviewer idle" + ("   last: " + last if last else ""), C_IDLE)
        return None

    def _tick(self) -> None:
        got = self._from_status()
        if got:
            text, bg = got
            self.label.configure(text=text, bg=bg); self.root.configure(bg=bg)
            self.root.after(POLL_MS, self._tick)
            return
        self._read_new()
        if self._size < 0:
            text, bg = "reviewer · log not found", C_DEAD
        elif self.current:
            sym, tf, when = self.current
            el = max(0, int((datetime.now() - when).total_seconds()))
            queued = max(0, len(self.pending) - 1)
            text = "● REVIEWER HAS THE CHARTS · %s %sm · %ds%s" % (
                sym, tf, el, ("  +%d queued" % queued) if queued else "")
            bg = C_BUSY
        elif self.restoring:
            text, bg = "◐ restoring your chart…", C_WAIT
        else:
            text = "○ reviewer idle" + ("   last: " + self.last if self.last else "")
            bg = C_IDLE
        self.label.configure(text=text, bg=bg)
        self.root.configure(bg=bg)
        self.root.after(POLL_MS, self._tick)


if __name__ == "__main__":
    Banner().root.mainloop()

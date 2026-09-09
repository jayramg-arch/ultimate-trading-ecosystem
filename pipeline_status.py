"""
pipeline_status.py — Per-phase status tracker for run_pipeline.py.

Writes a structured `pipeline_status.json` after each pipeline phase so the
dashboard can show a live grid of:

  Phase | Status | Duration | Records | Last Run

The file shape:
{
  "started_at": "2026-05-07T10:00:00",
  "ended_at":   "2026-05-07T10:14:33",
  "current":    "Phase 4.6 — Bull Screener",
  "phases": [
    {"name": "...", "status": "OK"|"FAIL"|"SKIP"|"RUNNING",
     "started_at": "...", "ended_at": "...", "duration_s": 12.3,
     "records": 42, "message": "free-form"},
    ...
  ]
}

Public API:
  ctx = PipelineRun()                 # creates empty status object, writes file
  with ctx.phase("Phase 1 — Scanners") as p:
      ...
      p.records = 240
      p.message = "240 stocks across 7 scanners"
  ctx.finalize()                       # writes ended_at

If a phase block raises, status="FAIL" and message=str(exc) are recorded
without re-raising — pipeline keeps moving (matches existing run_pipeline.py
philosophy of try/except per phase).
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

HERE        = os.path.dirname(os.path.abspath(__file__))
STATUS_PATH = os.path.join(HERE, "pipeline_status.json")


class _PhaseRecord:
    """Mutable handle handed to the `with ctx.phase(...)` block."""
    def __init__(self, name: str):
        self.name       = name
        self.status     = "RUNNING"
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.ended_at   = None
        self.duration_s = None
        self.records: Optional[int] = None
        self.message: str = ""

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "status":     self.status,
            "started_at": self.started_at,
            "ended_at":   self.ended_at,
            "duration_s": self.duration_s,
            "records":    self.records,
            "message":    self.message,
        }


class PipelineRun:
    """Holder for the whole pipeline run. Persists to pipeline_status.json
    after every phase boundary so the dashboard can reflect progress live."""

    def __init__(self, label: str = "Auto-Pilot Pipeline"):
        self.label      = label
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.ended_at: Optional[str] = None
        self.current: Optional[str]  = None
        self.phases: list[_PhaseRecord] = []
        self._save()

    def _save(self) -> None:
        payload = {
            "label":      self.label,
            "started_at": self.started_at,
            "ended_at":   self.ended_at,
            "current":    self.current,
            "phases":     [p.to_dict() for p in self.phases],
        }
        try:
            with open(STATUS_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=str)
        except Exception:
            pass  # status persistence is best-effort

    @contextmanager
    def phase(self, name: str):
        rec = _PhaseRecord(name)
        self.phases.append(rec)
        self.current = name
        self._save()
        t0 = time.time()
        try:
            yield rec
            if rec.status == "RUNNING":
                rec.status = "OK"
        except Exception as e:
            rec.status  = "FAIL"
            rec.message = (rec.message or "") + (" | " if rec.message else "") + f"exception: {e}"
        finally:
            rec.ended_at   = datetime.now().isoformat(timespec="seconds")
            rec.duration_s = round(time.time() - t0, 2)
            self._save()

    def skip(self, name: str, reason: str = "") -> None:
        """Record a phase as skipped without entering a block."""
        rec = _PhaseRecord(name)
        rec.status     = "SKIP"
        rec.ended_at   = rec.started_at
        rec.duration_s = 0.0
        rec.message    = reason
        self.phases.append(rec)
        self._save()

    def finalize(self) -> None:
        self.ended_at = datetime.now().isoformat(timespec="seconds")
        self.current  = None
        self._save()


def load_status() -> dict:
    """Read the most recent pipeline_status.json (for the dashboard)."""
    if not os.path.exists(STATUS_PATH):
        return {}
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def total_duration(status: dict) -> float:
    """Sum of all phase durations (seconds) from a status payload."""
    if not status:
        return 0.0
    return round(sum((p.get("duration_s") or 0) for p in status.get("phases", [])), 2)


__all__ = ["PipelineRun", "load_status", "total_duration", "STATUS_PATH"]

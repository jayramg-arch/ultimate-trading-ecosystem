"""gate_bucket = the gate count wherever it sits in the label (16-Oct-2026).

Labels can open with a plan-clock tag ('⏱D · 5/5 GO'); the first-word rule made every such
row's bucket '⏱D', so dedup treated 3/5 -> 5/5 on the wrong clock as one state."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gm_signal_log import gate_bucket  # noqa: E402


def test_clock_tag_does_not_become_the_bucket():
    assert gate_bucket("⏱D · 5/5 GO · PB") == "5/5"
    assert gate_bucket("⏱75/125 · 4/5 · weak bar · PA 2b") == "4/5"


def test_plain_and_blocked_rows():
    assert gate_bucket("5/5 GO") == "5/5"
    assert gate_bucket("3/5 · no loc") == "3/5"
    assert gate_bucket("⛔ Stage 4 · gates 3/5") == "⛔"
    assert gate_bucket("") == "?"

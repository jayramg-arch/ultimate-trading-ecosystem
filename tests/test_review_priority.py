"""review_priority (2-Oct-2026): the unit is the trigger bar; priority S4 alert > board > manual."""
import pandas as pd

import review_priority as rp


def test_trigger_bar_keys():
    assert rp.trigger_bar("2026-10-01 10:31", "75") == "2026-10-01|1"
    assert rp.trigger_bar("2026-10-01 14:30", "75") == "2026-10-01|4"
    assert rp.trigger_bar("2026-10-01 15:35", "75") == rp.trigger_bar("2026-10-01 17:10", "75")
    assert rp.trigger_bar("2026-10-01 10:00", "125") == "2026-09-30|3"
    assert rp.trigger_bar("2026-10-05 09:40", "D") == "2026-10-01|D"      # 2-Oct holiday skipped


def test_same_bar_keeps_highest_priority_different_bars_both_count():
    d = pd.DataFrame([
        {"ts": "2026-10-01 15:36", "symbol": "X", "tf": "75", "source": "manual"},
        {"ts": "2026-10-01 17:10", "symbol": "X", "tf": "75", "source": "board"},
        {"ts": "2026-10-01 15:40", "symbol": "X", "tf": "75", "source": "s4-alert"},
        {"ts": "2026-10-01 10:31", "symbol": "X", "tf": "75", "source": "manual"},
    ])
    p = rp.pick(d)
    assert len(p) == 2                                       # bar 1 and bar 5
    assert set(p["source"]) == {"s4-alert", "manual"}        # bar 5 -> the alert wins
    assert p[p["trigger_bar"].str.endswith("|1")]["source"].iloc[0] == "manual"

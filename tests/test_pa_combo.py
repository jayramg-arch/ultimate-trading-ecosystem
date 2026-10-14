"""PA -> now combo (14-Oct-2026): the last PA within 3 bars graded as one candle."""
import numpy as np
import pandas as pd
import gm_trigger_board as gtb


def _df(n=80):
    idx = pd.bdate_range("2026-01-01", periods=n)
    c = np.linspace(100, 120, n)
    return pd.DataFrame({"Open": c - 0.5, "High": c + 1, "Low": c - 1, "Close": c, "Volume": 1e5}, index=idx)


def _fires_on(dates):
    def fn(x, stage="", **kw):
        return [("p", x.index[-1] in dates, 3, "")]
    return fn


def test_today_firing_returns_none():
    df = _df()
    assert gtb.pa_combo(df, _fires_on({df.index[-1]})) is None


def test_finds_last_pa_and_grades_the_span():
    df = _df()
    pc = gtb.pa_combo(df, _fires_on({df.index[-3]}))
    assert pc["age"] == 2 and pc["held"] and pc["kept_low"]
    # span: PA open 100.0-ish, high/low over 3 bars, close 60% up the range -> neutral
    assert pc["grade"] == "neutral" and abs(pc["cpos"] - 0.6) < 0.01
    assert pc["pa_ts"] == str(df.index[-3])[:10]
    assert gtb.pa_combo_text(pc) == "PA 2b → combo Neutral 60% · held"


def test_failed_follow_through_is_named():
    df = _df()
    df.iloc[-1, df.columns.get_loc("Close")] = 90.0      # closed below the PA bar's low
    df.iloc[-1, df.columns.get_loc("Low")] = 89.0
    pc = gtb.pa_combo(df, _fires_on({df.index[-2]}))
    assert not pc["held"] and not pc["kept_low"] and pc["grade"] == "weak"
    assert gtb.pa_combo_text(pc).endswith("broke PA low")


def test_nothing_in_window():
    df = _df()
    assert gtb.pa_combo(df, _fires_on({df.index[-6]})) is None


def test_bar_read_shows_combo_only_on_daily_board():
    df = _df()
    pc = gtb.pa_combo(df, _fires_on({df.index[-2]}))
    ctx = {"bar": {"o": 100, "h": 102, "l": 99, "c": 101.5}, "pa_combo": pc, "_board_tf": "Daily"}
    assert "PA 1b → combo" in gtb.bar_read(ctx, "bull")
    ctx["_board_tf"] = "75m"
    assert "combo" not in gtb.bar_read(ctx, "bull")

"""Two-tier stop (12-Oct-2026): thesis = close-basis exit, disaster = the resting Dhan stop.
Pins who gets a close-below-thesis alert, on which clock, what rides the v67 book, and what
s4_take reads off a review."""
import sqlite3

import journal_path
import tv_push_v67_trail as v67
import tv_thesis_alerts as ta


def _db(tmp_path, rows):
    p = tmp_path / "j.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE journal (symbol TEXT, thesis_sl REAL, stoploss REAL, timeframe TEXT, status TEXT)")
    con.executemany("INSERT INTO journal VALUES (?,?,?,?,?)", rows)
    con.commit(); con.close()
    return str(p)


def test_only_two_tier_holdings_get_a_thesis_alert(tmp_path, monkeypatch):
    db = _db(tmp_path, [
        ("AAA", 110.0, 100.0, "Positional", "OPEN"),     # two-tier -> alert on the Daily close
        ("BBB", 50.0, 45.0, "Swing", "OPEN"),             # two-tier swing -> 125m clock
        ("CCC", 95.0, 95.0, "Positional", "OPEN"),        # thesis = stop: single tier, skipped
        ("DDD", 90.0, 95.0, "Positional", "OPEN"),        # thesis below the stop: superseded
        ("EEE", None, 95.0, "Positional", "OPEN"),        # no thesis
        ("FFF", 120.0, 100.0, "Positional", "CLOSED"),    # not held
    ])
    monkeypatch.setattr(journal_path, "JOURNAL_DB", db)
    items, skipped = ta.candidates()
    got = {c["sym"]: (c["level"], c["res"]) for c in items}
    assert got == {"AAA": (110.0, "1D"), "BBB": (50.0, "125")}
    assert len(skipped) == 3 and any("CCC" in s and "single tier" in s for s in skipped)


def test_trade_clock():
    assert ta.clock_of("Swing") == ("125", "125m")
    assert ta.clock_of("Positional") == ("1D", "Daily")
    assert ta.clock_of(None) == ("1D", "Daily")      # unknown = positional, as everywhere


def test_v67_book_carries_the_thesis_only_above_the_dhan_stop():
    base = {"window": 22, "mult": 4.5, "override": None, "anchored": False, "level": None}
    b = v67.book_string([dict(base, symbol="AAA", thesis=110.0, stoploss=100.0),
                         dict(base, symbol="CCC", thesis=95.0, stoploss=95.0)])
    assert "AAA=22,4.5000,0,T110.00" in b
    assert "CCC=22,4.5000,0;" in b + ";" and "T95" not in b


def test_s4_take_reads_the_thesis_and_daily_atr():
    import s4_take
    txt = ("RULING: TAKE\nPLAN x\n\n## PANEL READ\n"
           "S4 v11.30 │ core/72 | XYZ │ ATR(75) 30.00 (1.5%) · ATR(D) 70.72 (3.4%)\n"
           "Entry · SL · T1 · T2 | E 1446.3 │ SL 1382.4 │ INVAL 1287.7 zone distal (-12.3%) close-basis only\n")
    d = s4_take.parse_plan(txt)
    assert d["thesis"] == 1287.7 and d["atr_d"] == 70.72


def test_s5_rows_target_ticks_and_nse_tick_sizes():
    """S5 footprint rows (12-Oct-2026): ~10 rows per ATR, tick size from Dhan's scrip master."""
    import s5_rows
    assert s5_rows.target_ticks(58.93, 0.10) == 59        # TVSMOTOR 125m, matches S5's own hint
    assert s5_rows.target_ticks(0.5, 0.05) == 1           # floor at 1
    assert s5_rows.target_ticks(None, 0.05) is None and s5_rows.target_ticks(10, None) is None
    if s5_rows._ticks_table():                             # the master is a local data file
        assert s5_rows.tick_size("NSE:TVSMOTOR") == 0.10
        assert s5_rows.tick_size("NSE:PAGEIND") == 5.0

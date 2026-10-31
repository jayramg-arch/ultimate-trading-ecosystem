"""portfolio_review.post_checks - the house rules applied to a holding review (31-Oct-2026)."""
import portfolio_review as pr

ROW = {"ltp": 2405.5, "avg": 1613.23, "close": 2405.5, "atr": 71.72, "disaster": 2165.5,
       "thesis": 1952.1, "qty": 58, "budget": 15000.0}


def _rev(ruling, inv, stop):
    return "RECOMMENDATION\nRULING: %s - reason\nTHESIS INTACT - x\nINVALIDATION %s\nSTOP %s\n" % (ruling, inv, stop)


def test_add_on_a_loser_is_overruled(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: dict(ROW, ltp=1500.0, close=1500.0, disaster=1300.0,
                                                          thesis=1350.0, pnl_pct=-7.0))   # losing, no exit rule yet
    rev, out = pr.post_checks("X", _rev("ADD", "Daily close below 1400.00 (zone distal)", "KEEP 1300.00"))
    assert pr.ruling_word(rev) == "HOLD"
    assert any("no averaging down" in o for o in out)


def test_add_blocked_by_exposure_tier(monkeypatch):
    import house_policy
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    monkeypatch.setattr(house_policy, "exposure_status", lambda: {"adds_ok": False, "tier": "BEAR"})
    rev, out = pr.post_checks("X", _rev("ADD", "Daily close below 2250.00 (zone distal)", "KEEP 2165.50"))
    assert pr.ruling_word(rev) == "HOLD"
    assert any("BEAR tier" in o for o in out)


def test_invalidation_equal_to_dhan_stop_is_flagged(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2165.50 (Dhan stop)", "KEEP 2165.50"))
    assert any("is the Dhan stop itself" in o for o in out)


def test_invalidation_never_lowered(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: dict(ROW, disaster=1800.0))   # stop below the thesis
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 1900.00 (weekly level)", "KEEP 2165.50"))
    assert any("never lowered" in o for o in out)


def test_stop_raise_inside_three_atr_is_flagged(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2250.00 (zone)", "RAISE TO 2300.00 (swing low)"))
    assert any("inside 3 x ATR" in o for o in out)        # close 2405.5 - 3 x 71.72 = 2190.34


def test_drawdown_row_marks_a_broken_level(monkeypatch):
    import sl_board
    row = dict(ROW, symbol="X", thesis=2500.0, plan="Positional", close_src="t")
    monkeypatch.setattr(pr, "holding_row", lambda s: row)
    monkeypatch.setattr(sl_board, "_journal_rows", lambda: {})
    txt = pr.holding_block("X")
    assert "ALREADY THROUGH" in txt


def test_invalidation_below_the_dhan_stop_is_flagged(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2050.00 (swing low)", "KEEP 2165.50"))
    assert any("BELOW the Dhan stop" in o for o in out)


def test_report_ignores_the_appended_holding_block():
    body = "RULING: HOLD - x\nDRAWDOWN\n\n---\nHOLDING (computed...)\nDRAWDOWN from LTP (cost...)\n## PANEL READ\n"
    assert pr._line(pr._model_part(body), "DRAWDOWN") == ""


def test_exit_rule_overrules_reduce_on_a_big_loser(monkeypatch):
    # M&MFIN 31-Oct-2026: -32%, Chandelier above price, the model said REDUCE
    row = dict(ROW, ltp=261.7, close=261.7, avg=387.36, atr=12.53, disaster=251.5, thesis=309.2,
               chand=300.69, pnl_pct=-32.4)
    monkeypatch.setattr(pr, "holding_row", lambda s: row)
    rev, out = pr.post_checks("X", _rev("REDUCE", "Daily close below 253.40", "KEEP 251.50"))
    assert pr.ruling_word(rev) == "EXIT"
    assert any("overruled REDUCE to EXIT" in o and "-32.4%" in o for o in out)


def test_stage4_from_the_panel_forces_exit(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: dict(ROW, pnl_pct=5.0))
    read = "Structure basis | Stage 4 (3w leg/8w macro) | <30WMA"
    rev, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2250.00 (zone)", "KEEP 2165.50"), read)
    assert pr.ruling_word(rev) == "EXIT"


def test_structural_exit_held_off_in_grace(monkeypatch):
    import pyramid_logic, sl_board
    row = dict(ROW, close=2100.0, ltp=2100.0, thesis=2150.0, disaster=1900.0, pnl_pct=2.0)
    monkeypatch.setattr(pr, "holding_row", lambda s: row)
    monkeypatch.setattr(sl_board, "_journal_rows", lambda: {"X": {"entry_date": "2026-10-28"}})
    monkeypatch.setattr(pyramid_logic, "sessions_since", lambda d: 3)
    rev, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2000.00 (zone)", "KEEP 1900.00"))
    assert pr.ruling_word(rev) == "HOLD"
    assert any("held off - grace session 3/" in o for o in out)


def test_a_winner_with_no_exit_rule_keeps_its_ruling(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: dict(ROW, pnl_pct=49.1, chand=2165.5))
    rev, out = pr.post_checks("X", _rev("TRIM", "Daily close below 2250.00 (zone)", "KEEP 2165.50"),
                              "Structure basis | Stage 2 (12w)")
    assert pr.ruling_word(rev) == "TRIM"
    assert not any(o.startswith("EXIT-CHECK") for o in out)

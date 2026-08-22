"""Regression tests for sector_rotation_view.

Each test pins a behaviour that was either a real bug found on 21-Aug-2026 or a
deliberate design decision that a future edit could plausibly undo.
"""
import pandas as pd
import pytest

import sector_rotation_view as srv


def _summary(**overrides):
    rows = [
        {"Symbol": "CNXPHARMA", "Quadrant": "Leading",   "Distance": 6.1},
        {"Symbol": "CNXREALTY", "Quadrant": "Leading",   "Distance": 9.4},
        {"Symbol": "CNXAUTO",   "Quadrant": "Improving", "Distance": 3.0},
        {"Symbol": "CNXFMCG",   "Quadrant": "Weakening", "Distance": 4.2},
        {"Symbol": "CNXENERGY", "Quadrant": "Lagging",   "Distance": 7.7},
        {"Symbol": "NIFTY_FIN_SERVICE", "Quadrant": "Leading", "Distance": 2.0},
        {"Symbol": "CRSLDX",    "Quadrant": "Leading",   "Distance": 0.0},
    ]
    df = pd.DataFrame(rows)
    for k, v in overrides.items():
        df[k] = v
    df["Trajectory"] = "-"
    return df


# ---------------------------------------------------------------- leaderboard
def test_leaderboard_excludes_benchmark():
    """The benchmark is not a sector; ranking it first would be nonsense."""
    lb = srv.sector_leaderboard(_summary())
    assert "CRSLDX" not in " ".join(lb["Sector"])


def test_leaderboard_orders_leading_before_lagging():
    lb = srv.sector_leaderboard(_summary())
    states = lb["State"].tolist()
    assert states.index("Working") < states.index("Not working")


def test_leaderboard_far_from_centre_ranks_higher_within_quadrant():
    """Distance is the tie-break: further out is a stronger statement."""
    lb = srv.sector_leaderboard(_summary())
    lead = [s for s in lb["Sector"] if "\U0001F7E2" in s]
    assert "CNXREALTY" in lead[0]        # Distance 9.4 beats 6.1 and 2.0


def test_empty_input_returns_empty_not_raises():
    assert srv.sector_leaderboard(pd.DataFrame()).empty
    assert srv.candidates_by_sector(pd.DataFrame(), _summary()).empty
    assert all(x.empty for x in srv.holdings_by_sector(pd.DataFrame(), _summary()))


# ---------------------------------------------------------------- mapping
def test_index_alias_recovers_financials():
    """REAL BUG 21-Aug: sector_lookup says ^CNXFIN, the RRG universe plots
    NIFTY_FIN_SERVICE. Five board names silently fell out. Aliasing must map the
    synonym onto the charted index rather than losing the row."""
    assert srv._INDEX_ALIASES["CNXFIN"] == "NIFTY_FIN_SERVICE"
    m = srv.map_symbols_to_sectors([], _summary())
    assert isinstance(m, pd.DataFrame)


def test_unmapped_and_notcharted_are_distinct_states():
    """A mapping failure and a universe gap have different fixes, so they must
    not collapse into one bucket."""
    assert srv._UNKNOWN["state"] != srv._NOT_CHARTED["state"]
    assert srv._read_for("NotCharted")["state"] == "Not charted"
    assert srv._read_for("Whatever")["state"] == "Unknown"


def test_unresolvable_symbol_is_kept_not_dropped():
    """Honesty rule: never silently drop a name we could not map."""
    board = pd.DataFrame({"Symbol": ["ZZZNOTAREALTICKER"], "Overall": [50.0]})
    out = srv.candidates_by_sector(board, _summary())
    assert len(out) == 1


# ---------------------------------------------------------------- ranking
def test_sector_standing_outranks_overall():
    """The whole point of the view: a high-scoring name in a dead sector must
    sink below a lower-scoring name in a working one."""
    board = pd.DataFrame({
        "Symbol": ["ENERGYNAME", "PHARMANAME"],
        "Overall": [95.0, 40.0],
    })
    m = pd.DataFrame([
        {"Symbol": "ENERGYNAME", "Sector": "Energy", "Sector_Index": "CNXENERGY",
         "Quadrant": "Lagging", "Sector_Traj": "-", "Sector_Dist": 1.0},
        {"Symbol": "PHARMANAME", "Sector": "Pharma", "Sector_Index": "CNXPHARMA",
         "Quadrant": "Leading", "Sector_Traj": "-", "Sector_Dist": 1.0},
    ])
    orig = srv.map_symbols_to_sectors
    srv.map_symbols_to_sectors = lambda syms, sm: m
    try:
        out = srv.candidates_by_sector(board, _summary())
    finally:
        srv.map_symbols_to_sectors = orig
    assert out.iloc[0]["Symbol"] == "PHARMANAME"


def test_quadrant_read_never_used_as_a_filter():
    """Gate 5 was measured at +0.12pp and DISABLED. Sector standing ranks and
    warns; if an 'exclude'/'drop' key ever appears here, someone is re-adding a
    veto that the data does not support."""
    for v in srv.QUADRANT_READ.values():
        assert set(v) == {"state", "read", "action", "hold", "icon", "rank"}


# ---------------------------------------------------------------- holdings
def test_concentration_uses_the_order_gate_cap():
    """Page and order gate must not disagree about 'too concentrated'."""
    try:
        from pre_trade_gate import SECTOR_CAP_PCT
    except Exception:
        pytest.skip("pre_trade_gate unavailable")
    hold = pd.DataFrame({"Symbol": ["A", "B"], "Qty": [100, 1], "Avg": [1000.0, 1.0]})
    m = pd.DataFrame([
        {"Symbol": "A", "Sector": "Pharma", "Sector_Index": "CNXPHARMA",
         "Quadrant": "Leading", "Sector_Traj": "-", "Sector_Dist": 1.0},
        {"Symbol": "B", "Sector": "FMCG", "Sector_Index": "CNXFMCG",
         "Quadrant": "Weakening", "Sector_Traj": "-", "Sector_Dist": 1.0},
    ])
    orig = srv.map_symbols_to_sectors
    srv.map_symbols_to_sectors = lambda syms, sm: m
    try:
        _per, conc = srv.holdings_by_sector(hold, _summary())
    finally:
        srv.map_symbols_to_sectors = orig
    over = conc[conc["Sector"] == "Pharma"]["Cap Status"].iloc[0]
    assert "over" in over
    assert f"{SECTOR_CAP_PCT:.0f}" in over


def test_holdings_sorted_worst_standing_first():
    """This table exists to surface decay, so the bad news must be at the top."""
    hold = pd.DataFrame({"Symbol": ["GOOD", "BAD"], "Qty": [1, 1], "Avg": [1.0, 1.0]})
    m = pd.DataFrame([
        {"Symbol": "GOOD", "Sector": "Pharma", "Sector_Index": "CNXPHARMA",
         "Quadrant": "Leading", "Sector_Traj": "-", "Sector_Dist": 1.0},
        {"Symbol": "BAD", "Sector": "Energy", "Sector_Index": "CNXENERGY",
         "Quadrant": "Lagging", "Sector_Traj": "-", "Sector_Dist": 1.0},
    ])
    orig = srv.map_symbols_to_sectors
    srv.map_symbols_to_sectors = lambda syms, sm: m
    try:
        per, _conc = srv.holdings_by_sector(hold, _summary())
    finally:
        srv.map_symbols_to_sectors = orig
    assert per.iloc[0]["Symbol"] == "BAD"


# ---------------------------------------------------------------- rotation universe
def test_alias_never_overrides_a_charted_ticker():
    """REAL BUG 22-Aug: the rotation universe began plotting ^CNXFIN and dropping
    NIFTY_FIN_SERVICE, but the alias still redirected CNXFIN -> NIFTY_FIN_SERVICE
    unconditionally, which would have sent all 84 financials to Not-charted. An
    alias is a fallback for an UNCHARTED key, never an override."""
    sm = pd.DataFrame([{"Symbol": "CNXFIN", "Quadrant": "Leading", "Distance": 1.0,
                        "Trajectory": "-"}])

    class _SL:
        @staticmethod
        def get_sector_index(_):
            return "NSE:CNXFINANCE"

        @staticmethod
        def get_sector_name(_):
            return "Financial Services"

        @staticmethod
        def sector_to_yf(_):
            return "^CNXFIN"

    import sys
    prev = sys.modules.get("sector_lookup")
    sys.modules["sector_lookup"] = _SL
    try:
        m = srv.map_symbols_to_sectors(["ANYBANK"], sm)
    finally:
        if prev is not None:
            sys.modules["sector_lookup"] = prev
        else:
            sys.modules.pop("sector_lookup", None)
    assert m.iloc[0]["Quadrant"] == "Leading", "charted ^CNXFIN was aliased away"


def test_rotation_universe_has_no_duplicate_tickers():
    """Two names pointing at one ticker would plot the same sector twice."""
    import rrg_engine as re_
    from collections import Counter
    uni = re_.rotation_universe()
    dupes = {t: n for t, n in Counter(uni.values()).items() if n > 1}
    assert not dupes, f"same sector plotted twice: {dupes}"


def test_rotation_universe_covers_every_mapped_stock():
    """The guarantee this universe exists to provide. Measured 22-Aug: the plain
    sectoral table covered only 56% of mapped stocks (Infrastructure alone is 151
    names and lives in THEMATIC)."""
    import os
    import sqlite3
    import rrg_engine as re_
    import sector_lookup as sl
    db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sectors.db")
    if not os.path.exists(db):
        pytest.skip("sectors.db not present")
    tickers = {srv._clean(v) for v in re_.rotation_universe().values()}
    con = sqlite3.connect(db)
    try:
        rows = con.execute("SELECT sector_index, COUNT(*) FROM stock_sector "
                           "GROUP BY sector_index").fetchall()
    finally:
        con.close()
    uncovered = [(si, n) for si, n in rows
                 if srv._clean(sl.sector_to_yf(si) or "") not in tickers]
    assert not uncovered, f"sectors stocks map to but the chart cannot plot: {uncovered}"

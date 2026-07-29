"""Pins the strict-trend engine to Pine (dashboard v67.4.12 / Zigzag [Strict v6.3]).

Context: bull_screener and recovery_screener each carried a byte-identical copy of a
v1.4-era port, frozen before the Zigzag v6.2/v6.3 fixes reached Pine. The resulting
tDir errors were amplified into wrong Weinstein stages by the two tDir overrides in
compute_weekly_stage_and_wks, and stage in (1,2) is a screening gate — so Stage-4
names reached the Golden Matcher board. See strict_trend.py for the full write-up.

Each test below targets ONE divergence and was checked to go RED when that fix is
reverted; a test that cannot fail is not a regression test.
"""
import sys
import os

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import strict_trend as st  # noqa: E402


def zig(turns, pad=4):
    """Build High/Low series that pivot exactly at the given turning prices.

    `turns` alternates lows and highs. Between two turns the path is STRICTLY
    monotonic (endpoints excluded), so every interior turn is the unique extreme of
    its neighbourhood and is detected with piv_left/right=2. The first and last turns
    have only one flank, so — exactly as in Pine — they are not confirmed pivots;
    tests therefore lead with a throwaway turn.
    """
    prices = []
    for k in range(len(turns) - 1):
        a, b = turns[k], turns[k + 1]
        prices.append(a)
        for j in range(1, pad + 1):
            prices.append(a + (b - a) * j / (pad + 1))
    prices.append(turns[-1])
    idx = pd.date_range("2020-01-06", periods=len(prices), freq="W-MON")
    return (pd.Series([p + 0.001 for p in prices], index=idx),
            pd.Series([p - 0.001 for p in prices], index=idx))


def test_eq_threshold_is_canonical():
    """FIX 1. Zigzag v6.3 eq_pct=0.2% and the dashboard input default are both 0.002.
    The old port used 0.001; the dashboard's header COMMENT claims 0.005 and is stale."""
    assert st.EQ_THRESHOLD == 0.002


@pytest.mark.parametrize("new,prev,want", [
    (100.15, 100.0, "EH"),    # +0.15% -> inside 0.2% -> equal
    (100.30, 100.0, "HH"),    # +0.30% -> outside -> higher high
    (99.70, 100.0, "LH"),
    (100.0, float("nan"), "HH"),   # no reference -> Pine default
])
def test_classify_high_boundaries(new, prev, want):
    assert st.classify_high(new, prev) == want


@pytest.mark.parametrize("new,prev,want", [
    (99.85, 100.0, "EL"),
    (99.70, 100.0, "LL"),
    (100.30, 100.0, "HL"),
    (100.0, float("nan"), "LL"),
])
def test_classify_low_boundaries(new, prev, want):
    assert st.classify_low(new, prev) == want


def test_equal_low_does_not_confirm_uptrend():
    """FIX 3. Old port: `last_low_class in ("HL","EL")` let an EQUAL low confirm an
    uptrend. Pine v67.1: HH+HL strict only, EH/EL -> SIDEWAYS.

    Sequence (leading turn is a throwaway, see zig): low 100 -> high 120 -> low
    100.1 (EL, +0.1% = inside 0.2%) -> high 130, a confirmed HH landing on that EL.
    Old engine returned +1 here; strict must not.
    """
    h, l = zig([140.0, 100.0, 120.0, 100.1, 130.0, 110.0])
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert out.iloc[-1] != 1


def test_strictly_higher_low_still_confirms_uptrend():
    """Guard against over-correcting FIX 3 into 'nothing ever confirms'."""
    h, l = zig([140.0, 100.0, 120.0, 108.0, 130.0])
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert out.iloc[-1] == 1


def test_downtrend_is_detected():
    h, l = zig([100.0, 140.0, 110.0, 130.0, 95.0])
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert out.iloc[-1] == -1


def test_first_swing_low_not_dropped_when_history_opens_downward():
    """FIX 7 (the asymmetric bootstrap). Pine's pivot-LOW section opens with
    `activePivotType == "H" or na(activePivotType)`; the old Python had only == "H",
    so with no pivot established the first-ever swing LOW was silently dropped. Same
    defect the 14-Jun-2026 Zigzag audit fixed in Pine (v6.2 -> v6.3, Section 2).

    Fixture: the first CONFIRMED pivot is a low (100), and the next low (110) is
    higher. Whether that first low was locked decides HL (uptrend, +1) against a
    nan reference falling through to LL (0). Verified to return 0 when the seed
    branch is reverted.
    """
    h, l = zig([140.0, 100.0, 130.0, 110.0, 145.0])
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert out.iloc[-1] == 1, "first swing low was dropped — asymmetric bootstrap"


def test_flat_series_is_silent():
    idx = pd.date_range("2020-01-06", periods=60, freq="W-MON")
    h = pd.Series(np.full(60, 100.5), index=idx)
    l = pd.Series(np.full(60, 99.5), index=idx)
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert (out == 0).all()


def test_too_short_series_returns_zeros_not_error():
    idx = pd.date_range("2020-01-06", periods=3, freq="W-MON")
    h = pd.Series([1.0, 2.0, 3.0], index=idx)
    l = pd.Series([0.5, 1.5, 2.5], index=idx)
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert len(out) == 3 and (out == 0).all()


def test_output_shape_and_domain():
    h, l = zig([100.0, 120.0, 108.0, 130.0, 115.0, 140.0])
    out = st.compute_strict_trend(h, l, piv_left=2, piv_right=2)
    assert len(out) == len(h)
    assert set(out.unique()) <= {-1, 0, 1}


def test_both_screeners_share_one_engine():
    """The duplication is what let the two copies drift out of sync with Pine.
    If someone re-defines a local copy in either screener, this goes red."""
    import bull_screener as bs
    import recovery_screener as rs
    assert bs.compute_strict_trend is st.compute_strict_trend
    assert rs.compute_strict_trend is st.compute_strict_trend
    assert bs.classify_high is st.classify_high
    assert rs.classify_low is st.classify_low


# ---------------------------------------------------------------------------
# GOLDEN VECTORS — real NSE weekly High/Low (90 bars, 5y series, Dhan feed),
# embedded so the test stays hermetic. Synthetic zig-zags are too clean: they never
# produce equal pivots, extensions or messy bootstraps, so they cannot exercise most
# of the engine. These two names come from the 29-Jul-2026 board-vs-Pine diff.
#
# This is a CHANGE DETECTOR, not a correctness proof. It pins current behaviour so a
# silent regression is impossible; an INTENTIONAL engine change is expected to fail
# it, and the vector should then be regenerated deliberately.
#
# Mutation-verified coverage (each fix reverted one at a time):
#   caught here .......... fix 4 (re-classification), fix 5 (projection gate),
#                          fix 7 (bootstrap seed)
#   caught by the targeted tests above ... fix 1 (eq threshold), fix 3 (strict
#                          confirmation), fix 7
#   NOT COVERED by any failing test ...... fix 2 (extension re-classifies against
#                          prevLocked*) and fix 6 (syncBars +1). Both need an
#                          extension event / window-boundary case these fixtures do
#                          not contain. Reverting either passes the whole suite —
#                          known gap, stated rather than papered over.
# ---------------------------------------------------------------------------

CIPLA_H = [
    1599.75, 1505.15, 1547.7, 1549.4, 1484.75, 1510.05, 1512.75, 1547.85, 1513.0,
    1463.95, 1464.8, 1491.0, 1481.85, 1493.0, 1502.0, 1489.0, 1471.1, 1482.2, 1528.9,
    1535.0, 1523.3, 1488.5, 1522.0, 1566.7, 1570.8, 1549.0, 1539.9, 1511.7, 1493.9,
    1505.9, 1537.9, 1541.0, 1522.4, 1525.0, 1519.2, 1492.5, 1553.7, 1579.9, 1519.3,
    1574.8, 1602.0, 1607.8, 1599.0, 1578.3, 1584.9, 1583.2, 1537.8, 1569.0, 1582.1,
    1673.0, 1593.8, 1524.0, 1534.9, 1538.4, 1535.8, 1536.3, 1524.7, 1520.1, 1522.5,
    1517.8, 1539.7, 1469.4, 1398.4, 1343.0, 1381.3, 1358.0, 1358.0, 1364.9, 1354.5,
    1341.7, 1327.9, 1252.9, 1257.0, 1239.0, 1244.5, 1308.4, 1329.8, 1379.5, 1444.5,
    1442.1, 1432.0, 1413.6, 1405.0, 1397.9, 1461.0, 1490.1, 1482.0, 1454.5, 1466.6,
    1447.8
]
CIPLA_L = [
    1490.25, 1453.85, 1468.5, 1470.1, 1423.8, 1436.1, 1458.8, 1495.1, 1465.15, 1429.85,
    1408.0, 1366.1, 1406.15, 1431.55, 1426.35, 1400.0, 1389.3, 1437.75, 1455.7, 1434.45,
    1390.05, 1335.0, 1462.1, 1502.7, 1513.5, 1463.7, 1462.2, 1451.2, 1457.1, 1458.0,
    1480.0, 1480.2, 1482.1, 1493.3, 1463.2, 1468.2, 1454.5, 1494.0, 1464.1, 1480.2,
    1533.4, 1567.8, 1550.0, 1533.1, 1546.1, 1475.2, 1485.3, 1490.8, 1537.1, 1577.9,
    1500.0, 1490.3, 1503.9, 1505.4, 1500.0, 1495.1, 1484.8, 1491.0, 1490.2, 1475.9,
    1455.0, 1367.2, 1303.0, 1281.7, 1293.1, 1315.8, 1323.7, 1308.8, 1311.0, 1292.7,
    1235.4, 1216.6, 1165.7, 1170.0, 1203.2, 1222.0, 1296.3, 1313.6, 1274.7, 1392.0,
    1382.7, 1354.0, 1371.1, 1341.1, 1370.6, 1441.5, 1426.4, 1404.0, 1366.1, 1392.8
]
CIPLA_GOLDEN = "................................uuuuuuuuuuuuuuuuuuuuuuuuuuuu.......................ddddddd"

LODHA_H = [
    1291.0, 1294.0, 1326.4, 1397.4, 1442.1, 1523.0, 1465.8, 1461.2, 1448.0, 1259.9,
    1222.5, 1292.0, 1305.05, 1244.95, 1222.35, 1215.0, 1172.75, 1149.95, 1238.1, 1255.0,
    1231.75, 1149.8, 1262.4, 1390.0, 1382.5, 1359.0, 1411.8, 1434.0, 1483.5, 1529.9,
    1531.0, 1504.0, 1509.8, 1430.0, 1422.0, 1458.7, 1461.5, 1284.0, 1247.1, 1239.9,
    1327.6, 1284.9, 1226.4, 1217.2, 1223.0, 1229.0, 1165.0, 1161.3, 1197.5, 1199.5,
    1214.0, 1244.0, 1243.0, 1232.0, 1181.0, 1158.0, 1115.9, 1129.3, 1108.7, 1089.1,
    1138.5, 1088.4, 1073.6, 977.0, 1066.55, 1100.0, 1113.2, 1085.4, 978.7, 919.7, 874.6,
    789.0, 702.95, 842.0, 878.7, 894.8, 921.45, 974.9, 956.6, 904.0, 969.0, 942.0,
    901.0, 942.95, 972.0, 1062.0, 1225.2, 1219.95, 1205.0, 1316.4
]
LODHA_L = [
    1161.75, 1163.05, 1212.15, 1246.0, 1354.05, 1392.0, 1384.25, 1346.6, 1276.85,
    1110.0, 1053.2, 1087.4, 1194.1, 1135.2, 1123.6, 1120.05, 1087.05, 1050.15, 1035.15,
    1188.45, 1147.0, 1076.0, 1145.0, 1239.0, 1272.6, 1225.0, 1250.0, 1375.0, 1411.2,
    1412.1, 1420.0, 1415.2, 1415.9, 1354.3, 1352.0, 1387.0, 1275.1, 1190.6, 1196.0,
    1198.1, 1226.1, 1182.6, 1168.0, 1161.1, 1159.6, 1136.1, 1108.0, 1098.8, 1136.5,
    1168.2, 1163.2, 1196.8, 1195.1, 1161.9, 1145.3, 1093.6, 1056.2, 1047.6, 1069.7,
    1053.0, 1052.8, 1040.2, 892.7, 863.8, 918.0, 1045.9, 1057.35, 984.7, 885.95, 850.45,
    792.3, 691.85, 650.8, 686.65, 784.3, 833.8, 836.35, 901.0, 845.0, 830.2, 897.05,
    856.5, 848.0, 900.15, 905.85, 931.0, 1049.1, 1144.2, 1124.0, 1150.1
]
LODHA_GOLDEN = "....................................................uuuudddddddddddddddddddddddddddddddddd"


@pytest.mark.parametrize("name,highs,lows,golden", [
    ("CIPLA", CIPLA_H, CIPLA_L, CIPLA_GOLDEN),
    ("LODHA", LODHA_H, LODHA_L, LODHA_GOLDEN),
])
def test_golden_vector_real_weekly(name, highs, lows, golden):
    out = st.compute_strict_trend(pd.Series(highs), pd.Series(lows),
                                  piv_left=5, piv_right=5)
    got = "".join({-1: "d", 0: ".", 1: "u"}[int(v)] for v in out)
    assert got == golden, (
        f"{name}: strict-trend output changed.\n  was {golden}\n  now {got}\n"
        "If this change was intentional, regenerate the vector deliberately."
    )

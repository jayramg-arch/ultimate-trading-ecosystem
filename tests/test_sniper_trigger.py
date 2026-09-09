import pytest
from sniper_trigger import _regime_size_multiplier, _adr_size_multiplier, calculate_position_size

def test_regime_size_multiplier():
    assert _regime_size_multiplier(None) == 1.00
    assert _regime_size_multiplier(10) == 1.50
    assert _regime_size_multiplier(0) == 0.30
    assert _regime_size_multiplier(5) == 0.90
    assert _regime_size_multiplier(2) == 0.54 # 0.3 + 0.2*1.2 = 0.54

def test_adr_size_multiplier():
    assert _adr_size_multiplier(None) == 1.00
    assert _adr_size_multiplier(1.5) == 1.00
    assert _adr_size_multiplier(2.5) == 0.85
    assert _adr_size_multiplier(4.0) == 0.70
    assert _adr_size_multiplier(6.0) == 0.50

def test_calculate_position_size():
    # Capital = 100,000. Risk per trade = 1% = 1,000.
    # Entry = 100, Stoploss = 90. Risk per share = 10.
    # Qty = 1,000 / 10 = 100.
    qty, risk_ps, max_risk, detail = calculate_position_size(100000, 100, 90)
    assert qty == 100
    assert risk_ps == 10
    assert max_risk == 1000
    assert detail["base_risk_pct"] == 1.0

def test_calculate_position_size_with_multipliers():
    # Base risk = 1,000. Regime = 0 (multiplier 0.3). ADR = 6.0 (multiplier 0.5)
    # Total multiplier = 0.15. Final risk = 150.
    # Risk per share = 10.
    # Qty = 15.
    qty, risk_ps, max_risk, detail = calculate_position_size(100000, 100, 90, regime_score=0, adr_pct=6.0)
    assert qty == 15
    assert risk_ps == 10
    assert max_risk == 150
    assert detail["regime_mult"] == 0.30
    assert detail["adr_mult"] == 0.50

def test_calculate_position_size_invalid():
    # Entry <= Stoploss
    qty, risk_ps, max_risk, detail = calculate_position_size(100000, 90, 100)
    assert qty is None

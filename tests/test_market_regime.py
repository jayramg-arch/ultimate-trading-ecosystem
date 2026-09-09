import pytest
import pandas as pd
import numpy as np
from market_regime import compute_distribution_days, detect_follow_through, _verdict

def test_verdict():
    assert _verdict(10) == "RISK-ON / Bull Healthy"
    assert _verdict(8) == "RISK-ON / Bull Healthy"
    assert _verdict(7) == "Cautious Bull"
    assert _verdict(6) == "Cautious Bull"
    assert _verdict(5) == "Neutral / Choppy"
    assert _verdict(4) == "Neutral / Choppy"
    assert _verdict(3) == "Defensive"
    assert _verdict(2) == "Defensive"
    assert _verdict(1) == "Bear / Cash"
    assert _verdict(0) == "Bear / Cash"

def test_compute_distribution_days_empty():
    df = pd.DataFrame()
    res = compute_distribution_days(df)
    assert res["count"] == 0
    assert res["stress"] is False

def test_compute_distribution_days_trigger():
    # Construct a dataframe that triggers distribution days
    # Distribution day = drop >= 0.2% and volume > prev day
    dates = pd.date_range(start="2026-01-01", periods=10)
    data = {
        "Close": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91], # consistent drops of > 0.2%
        "Volume": [100, 110, 120, 130, 140, 150, 160, 170, 180, 190] # volume consistently higher
    }
    df = pd.DataFrame(data, index=dates)
    res = compute_distribution_days(df, drop_pct=0.2, window=5)
    
    # 5 recent rows (indices 5, 6, 7, 8, 9). 
    # Drops from prev day are > 0.2% and volume higher.
    # The first difference needs the prior day, so indices 5, 6, 7, 8, 9 are all DDs.
    assert res["count"] == 5
    assert res["stress"] is True

def test_detect_follow_through_insufficient_data():
    df = pd.DataFrame({"Close": [100], "High": [100], "Volume": [100]})
    res = detect_follow_through(df)
    assert res["active"] is False
    assert "insufficient data" in res["details"]

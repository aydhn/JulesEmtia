import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.features import add_features

def test_add_features():
    np.random.seed(42)
    close_prices = np.cumsum(np.random.randn(250)) + 100
    df = pd.DataFrame({
        'Open': close_prices - 1,
        'High': close_prices + 2,
        'Low': close_prices - 2,
        'Close': close_prices,
        'Volume': np.random.randint(1000, 5000, size=250)
    })
    df.index = pd.date_range('2020-01-01', periods=250)

    res = add_features(df)
    assert not res.empty
    assert 'EMA_50' in res.columns
    assert 'EMA_200' in res.columns
    assert 'RSI_14' in res.columns
    assert 'ATR_14' in res.columns

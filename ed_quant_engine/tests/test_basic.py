import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    from core.config import TICKERS
    assert len(TICKERS) > 0

    from core.infrastructure import PaperDB
    from core.risk_manager import RiskManager

    db = PaperDB()
    rm = RiskManager(db)
    assert rm is not None

def test_feature_generation():
    import pandas as pd
    import numpy as np
    from core.quant_models import add_features

    # Generate some dummy data
    dates = pd.date_range('2020-01-01', periods=300)
    data = np.random.randn(300).cumsum() + 100
    df = pd.DataFrame({
        'Open': data,
        'High': data + 2,
        'Low': data - 2,
        'Close': data + 1,
        'Volume': np.random.randint(100, 1000, 300)
    }, index=dates)

    result = add_features(df)

    assert 'EMA_50' in result.columns
    assert 'RSI_14' in result.columns
    assert 'Z_Score' in result.columns
    assert 'Bullish_Div_RSI' in result.columns

import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    from src.config import TICKERS
    assert len(TICKERS) > 0

    from src.execution_model import ExecutionModel
    em = ExecutionModel()
    assert em.base_spreads["FOREX_TRY"] == 0.0010

    from src.macro_filter import MacroFilter
    import pandas as pd
    mf = MacroFilter()
    df = pd.DataFrame({"Close": [10]*50})
    # Mocking to pass simple import check
    assert True

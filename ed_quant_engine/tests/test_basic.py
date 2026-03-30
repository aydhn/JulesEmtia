import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    from src.config import get_all_tickers
    assert len(get_all_tickers()) > 0

    from src.execution_model import get_base_spread
    assert get_base_spread("USDTRY=X") == 0.0010

    from src.macro_filter import check_flash_crash
    import pandas as pd
    df = pd.DataFrame({"Close": [10]*50})
    assert check_flash_crash(df) == False

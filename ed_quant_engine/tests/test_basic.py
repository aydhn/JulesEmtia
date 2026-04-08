import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    from core.config import TICKERS
    assert len(TICKERS) > 0

    from core.quant_models import RiskManager
    from core.infrastructure import PaperDB

    db = PaperDB()
    rm = RiskManager(db)
    assert rm is not None

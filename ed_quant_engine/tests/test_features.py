import pytest
import pandas as pd
from src.features import calculate_mtf_features

def test_calculate_mtf_features_empty():
    df1 = pd.DataFrame()
    df2 = pd.DataFrame()
    res = calculate_mtf_features(df1, df2)
    assert res.empty

import pandas as pd
from data.data_loader import fetch_data_with_retry

def calculate_correlation(tickers: list) -> pd.DataFrame:
    dfs = []
    for ticker in tickers:
        df = fetch_data_with_retry(ticker, "1d", period="30d")
        if not df.empty:
            dfs.append(df['Close'].rename(ticker))
    if dfs:
        df_combined = pd.concat(dfs, axis=1)
        return df_combined.corr()
    return pd.DataFrame()

def is_correlated(new_ticker: str, open_tickers: list, corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
    for ot in open_tickers:
        if new_ticker in corr_matrix.columns and ot in corr_matrix.columns:
            if corr_matrix.loc[new_ticker, ot] > threshold:
                return True
    return False

def calculate_position_size(capital: float, entry_price: float, sl_price: float, win_rate: float = 0.6) -> float:
    risk_per_trade = capital * 0.02 # Base risk 2%
    kelly_fraction = (win_rate - (1 - win_rate)) / 2 # Half Kelly
    kelly_fraction = max(0.005, min(0.04, kelly_fraction)) # Min 0.5%, Max 4%
    risk_amount = capital * kelly_fraction
    distance = abs(entry_price - sl_price)
    return risk_amount / distance if distance > 0 else 0

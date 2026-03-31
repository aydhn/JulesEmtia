import pandas as pd
import numpy as np
from typing import Dict, Any, List
from data_loader import fetch_historical_data
from strategy import generate_signals
from features import add_features
from macro_filter import get_macro_regime
from ml_validator import validate_signal_with_ml
from sentiment_filter import SentimentAnalyzer, check_sentiment_veto
from portfolio_manager import calculate_correlation_matrix, check_correlation_veto
from execution_model import calculate_slippage_and_spread
from logger import setup_logger

logger = setup_logger("Backtester")

def run_historical_backtest(ticker: str, start_date: str = "2020-01-01", end_date: str = "2024-01-01", initial_balance: float = 10000.0) -> Dict[str, Any]:
    """Runs a highly efficient, vectorized/iterative backtest simulating trading strategy across historical data."""
    logger.info(f"Backtest Başlatılıyor [{ticker}] Dönem: {start_date} -> {end_date}")

    # 1. Fetch multi-timeframe data
    import yfinance as yf
    try:
        # Fetching 1D and 1H simultaneously
        htf_df = yf.download(ticker, start=start_date, end=end_date, interval="1d", progress=False)
        ltf_df = yf.download(ticker, start=start_date, end=end_date, interval="1h", progress=False)
    except Exception as e:
        logger.error(f"Backtest verisi alınamadı: {str(e)}")
        return {}

    if htf_df.empty or ltf_df.empty:
        return {}

    # Flatten columns
    if isinstance(htf_df.columns, pd.MultiIndex):
        htf_df.columns = [col[0] for col in htf_df.columns]
    if isinstance(ltf_df.columns, pd.MultiIndex):
        ltf_df.columns = [col[0] for col in ltf_df.columns]

    # Timezone strip
    htf_df.index = htf_df.index.tz_localize(None)
    ltf_df.index = ltf_df.index.tz_localize(None)

    # Calculate indicators
    htf_df = add_features(htf_df)
    ltf_df = add_features(ltf_df)

    # Shift HTF by 1 to prevent lookahead
    htf_shifted = htf_df.shift(1).reset_index()
    ltf_df_reset = ltf_df.reset_index()

    # Align DataFrames
    merged_df = pd.merge_asof(
        ltf_df_reset.sort_values('Datetime'),
        htf_shifted.sort_values('Date'),
        left_on='Datetime',
        right_on='Date',
        direction='backward',
        suffixes=('', '_HTF')
    )
    merged_df.set_index('Datetime', inplace=True)

    balance = initial_balance
    trades = []
    open_trade = None

    # Simülasyon Döngüsü (Iterative approach needed for trailing stop path-dependence)
    for i in range(200, len(merged_df)):
        current_bar = merged_df.iloc[i]

        # 1. Check open trade for exit (TP/SL)
        if open_trade:
            # Trailing stop and breakeven simulation logic
            current_price = current_bar['Close']
            entry_price = open_trade['entry_price']
            direction = open_trade['direction']
            sl = open_trade['sl_price']
            tp = open_trade['tp_price']
            atr = current_bar['ATRr_14']

            pnl = 0.0
            closed = False

            if direction == "Long":
                # Breakeven
                if current_price > entry_price + (1.5 * atr) and sl < entry_price:
                    open_trade['sl_price'] = entry_price
                # Trail
                elif current_price > entry_price + (2.0 * atr):
                    new_sl = current_price - (1.5 * atr)
                    if new_sl > sl: open_trade['sl_price'] = new_sl

                if current_bar['Low'] <= sl: # Hit stop loss
                    # Exit with slippage penalty
                    exit_price = sl * (1 - 0.0005)
                    pnl = (exit_price - entry_price) * open_trade['size']
                    closed = True
                elif current_bar['High'] >= tp: # Hit take profit
                    exit_price = tp * (1 - 0.0005)
                    pnl = (exit_price - entry_price) * open_trade['size']
                    closed = True

            elif direction == "Short":
                # Breakeven
                if current_price < entry_price - (1.5 * atr) and sl > entry_price:
                    open_trade['sl_price'] = entry_price
                # Trail
                elif current_price < entry_price - (2.0 * atr):
                    new_sl = current_price + (1.5 * atr)
                    if new_sl < sl: open_trade['sl_price'] = new_sl

                if current_bar['High'] >= sl: # Hit stop loss
                    exit_price = sl * (1 + 0.0005)
                    pnl = (entry_price - exit_price) * open_trade['size']
                    closed = True
                elif current_bar['Low'] <= tp: # Hit take profit
                    exit_price = tp * (1 + 0.0005)
                    pnl = (entry_price - exit_price) * open_trade['size']
                    closed = True

            if closed:
                balance += pnl
                trades.append({
                    "entry_time": open_trade['entry_time'],
                    "exit_time": current_bar.name,
                    "direction": direction,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "balance": balance
                })
                open_trade = None
            continue # If trade is open, we don't look for new entries

        # 2. Look for new entry
        # We pass a slice of the dataframe ending at the previous candle to the strategy to mimic live conditions
        window_df = merged_df.iloc[i-200:i+1] # Provide enough lookback, up to current CLOSED candle

        signal = generate_signals(window_df, ticker)

        if signal:
            direction = signal['direction']

            # MTF Filter check
            if 'EMA_50_HTF' in current_bar:
                htf_ema = current_bar['EMA_50_HTF']
                htf_close = current_bar['Close_HTF']
                if (direction == "Long" and htf_close < htf_ema) or \
                   (direction == "Short" and htf_close > htf_ema):
                    continue

            # Calculate Entry Price with Spread & Slippage Phase 21
            cost_pct = 0.0005 + 0.0005 # 0.05% spread half + 0.05% slip
            entry_price = signal['entry_price'] * (1 + cost_pct) if direction == "Long" else signal['entry_price'] * (1 - cost_pct)

            # Simplified Position Sizing (Fixed 2% Risk)
            risk_amount = balance * 0.02
            stop_distance = abs(entry_price - signal['sl_price'])
            if stop_distance == 0: continue

            lot_size = risk_amount / stop_distance

            open_trade = {
                "entry_time": current_bar.name,
                "direction": direction,
                "entry_price": entry_price,
                "sl_price": signal['sl_price'],
                "tp_price": signal['tp_price'],
                "size": lot_size
            }

    # Generate Performance Metrics
    df_trades = pd.DataFrame(trades)
    if df_trades.empty:
        logger.warning(f"Backtest Sonucu [{ticker}]: İşlem bulunamadı.")
        return {}

    total_trades = len(df_trades)
    winning_trades = df_trades[df_trades['pnl'] > 0]
    losing_trades = df_trades[df_trades['pnl'] <= 0]

    win_rate = (len(winning_trades) / total_trades) * 100
    gross_profit = winning_trades['pnl'].sum()
    gross_loss = abs(losing_trades['pnl'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    net_pnl = df_trades['pnl'].sum()

    # Calculate Max Drawdown
    df_trades['equity'] = initial_balance + df_trades['pnl'].cumsum()
    df_trades['peak'] = df_trades['equity'].cummax()
    df_trades['drawdown'] = (df_trades['equity'] - df_trades['peak']) / df_trades['peak'] * 100
    max_drawdown = df_trades['drawdown'].min()

    logger.info(f"Backtest Özeti [{ticker}]: İşlem Sayısı: {total_trades} | Net PnL: ${net_pnl:.2f} | Win Rate: %{win_rate:.2f} | PF: {profit_factor:.2f} | Max DD: %{max_drawdown:.2f}")

    return {
        "ticker": ticker,
        "total_trades": total_trades,
        "net_pnl": net_pnl,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "equity_curve": df_trades[['exit_time', 'equity']].to_dict('records')
    }

import pandas as pd
import numpy as np
from logger import get_logger

log = get_logger()

def backtest_strategy(df: pd.DataFrame, params: dict = None) -> dict:
    """
    Fast iterative historical backtest (Phase 7).
    Calculates Win Rate, Profit Factor, Max Drawdown, Total PnL vs Benchmark.
    Applies 0.1% Slippage and 0.05% Commission.
    """
    if df is None or df.empty:
        return {"win_rate": 0, "profit_factor": 0, "max_dd": 0, "total_pnl": 0, "trades": 0}

    slippage = 0.001
    commission = 0.0005

    if 'Close_HTF' in df.columns:
        htf_up = (df['Close_HTF'] > df.get('EMA_50_HTF', 0)) & (df.get('MACD_HTF', 0) > df.get('MACD_Signal_HTF', 0))
        htf_dn = (df['Close_HTF'] < df.get('EMA_50_HTF', 0)) & (df.get('MACD_HTF', 0) < df.get('MACD_Signal_HTF', 0))
    else:
        htf_up = pd.Series(True, index=df.index)
        htf_dn = pd.Series(True, index=df.index)

    ltf_oversold = (df.get('RSI_14', 50) < 30) | (df['Close'] <= df.get('BB_Lower', 0))
    ltf_overbought = (df.get('RSI_14', 50) > 70) | (df['Close'] >= df.get('BB_Upper', 999999))

    long_signals = htf_up & ltf_oversold
    short_signals = htf_dn & ltf_overbought

    trades = []
    in_position = False
    entry_price = 0
    sl = 0
    tp = 0
    direction = 0

    closes = df['Close'].values
    atrs = df['ATR_14'].values if 'ATR_14' in df.columns else np.zeros(len(df))
    long_sigs = long_signals.values
    short_sigs = short_signals.values

    for i in range(len(closes)):
        price = closes[i]

        if in_position:
            hit_tp = (direction == 1 and price >= tp) or (direction == -1 and price <= tp)
            hit_sl = (direction == 1 and price <= sl) or (direction == -1 and price >= sl)

            if hit_tp or hit_sl:
                exit_price = price
                exit_price = exit_price * (1 - slippage) if direction == 1 else exit_price * (1 + slippage)
                cost = exit_price * commission

                pnl = (exit_price - entry_price) if direction == 1 else (entry_price - exit_price)
                pnl -= cost

                trades.append(pnl / entry_price)
                in_position = False
        else:
            if long_sigs[i]:
                direction = 1
                entry_price = price * (1 + slippage)
                cost = entry_price * commission
                entry_price += cost
                sl = entry_price - (1.5 * atrs[i])
                tp = entry_price + (3.0 * atrs[i])
                in_position = True
            elif short_sigs[i]:
                direction = -1
                entry_price = price * (1 - slippage)
                cost = entry_price * commission
                entry_price -= cost
                sl = entry_price + (1.5 * atrs[i])
                tp = entry_price - (3.0 * atrs[i])
                in_position = True

    if not trades:
        return {"win_rate": 0, "profit_factor": 0, "max_dd": 0, "total_pnl": 0, "trades": 0}

    trades_arr = np.array(trades)
    wins = trades_arr[trades_arr > 0]
    losses = trades_arr[trades_arr <= 0]

    win_rate = len(wins) / len(trades_arr)
    gross_win = np.sum(wins) if len(wins) > 0 else 0
    gross_loss = np.abs(np.sum(losses)) if len(losses) > 0 else 0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0

    total_pnl = np.sum(trades_arr)

    cum_ret = np.cumprod(1 + trades_arr)
    running_max = np.maximum.accumulate(cum_ret)
    dd = (cum_ret - running_max) / running_max
    max_dd = np.min(dd) if len(dd) > 0 else 0

    return {
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_dd": abs(max_dd),
        "total_pnl": total_pnl,
        "trades": len(trades_arr)
    }

def walk_forward_optimization(df: pd.DataFrame, n_windows: int = 4):
    """
    Walk-Forward Optimization (Phase 14).
    Calculates Walk-Forward Efficiency (WFE) to prevent curve-fitting.
    If WFE < 50%, the parameters are rejected as overfitted.
    """
    if df is None or len(df) < 100:
        return pd.DataFrame()

    window_size = len(df) // (n_windows + 1)
    results = []

    for i in range(n_windows):
        start_is = i * window_size
        end_is = start_is + window_size * 2
        end_oos = end_is + window_size

        if end_oos > len(df):
            break

        df_is = df.iloc[start_is:end_is]
        df_oos = df.iloc[end_is:end_oos]

        res_is = backtest_strategy(df_is)
        res_oos = backtest_strategy(df_oos)

        wfe = res_oos['total_pnl'] / res_is['total_pnl'] if res_is['total_pnl'] > 0 else 0

        status = "Robust" if wfe >= 0.5 and res_oos['total_pnl'] > 0 else "Overfitted"

        results.append({
            "Window": i+1,
            "IS_PnL": res_is['total_pnl'],
            "OOS_PnL": res_oos['total_pnl'],
            "WFE": wfe,
            "Status": status
        })

    res_df = pd.DataFrame(results)
    log.info(f"WFO Results:\n{res_df}")
    return res_df

def run_monte_carlo(pnl_pcts: list, n_simulations=10000, initial_capital=10000.0) -> dict:
    """
    Monte Carlo Risk of Ruin & Drawdown Simulation (Phase 22).
    Vectorised operations to prevent CPU hogging.
    Returns the expected maximum drawdown at 95% and 99% Confidence Intervals,
    along with Risk of Ruin (probability of losing 50% capital).
    """
    if not pnl_pcts or len(pnl_pcts) < 10:
        return {"max_dd_95": 0, "max_dd_99": 0, "risk_of_ruin": 0}

    pnl_array = np.array(pnl_pcts)
    n_trades = len(pnl_array)

    # Random choice with replacement (10,000 paths of n_trades length)
    sim_paths = np.random.choice(pnl_array, size=(n_simulations, n_trades), replace=True)

    # Calculate cumulative returns
    cum_returns = np.cumprod(1 + sim_paths, axis=1) * initial_capital

    # Calculate Drawdowns
    running_max = np.maximum.accumulate(cum_returns, axis=1)
    drawdowns = (cum_returns - running_max) / running_max
    max_drawdowns = np.min(drawdowns, axis=1) # Min because drawdowns are negative

    max_dd_95 = np.percentile(max_drawdowns, 5) # 5th percentile of negative numbers
    max_dd_99 = np.percentile(max_drawdowns, 1) # 1st percentile

    # Risk of Ruin: paths that drop below 50% of initial
    ruined_paths = np.sum(np.min(cum_returns, axis=1) < (initial_capital * 0.5))
    risk_of_ruin = ruined_paths / n_simulations

    log.info(f"Monte Carlo Results: 99% DD={max_dd_99:.2%}, Ruin={risk_of_ruin:.2%}")
    return {"max_dd_95": abs(max_dd_95), "max_dd_99": abs(max_dd_99), "risk_of_ruin": risk_of_ruin}

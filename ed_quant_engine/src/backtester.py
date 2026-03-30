import pandas as pd
import numpy as np
from typing import List, Dict
from .logger import log_info, log_error

def run_vectorized_backtest(df: pd.DataFrame, direction: str, sl_multiplier: float = 1.5, tp_multiplier: float = 3.0, slippage_pct: float = 0.001) -> dict:
    """
    Sıfır Bütçeli (Harici Kütüphanesiz) Vektörel (Pandas Shift tabanlı) Backtest Motoru.
    Geleceği görmeyi engeller (Lookahead Bias korumalıdır).
    İşlemlere kayma (Slippage %0.1 varsayılan) ekler.
    """
    if len(df) < 100:
        return {"Trades": 0, "WinRate": 0, "ProfitFactor": 0, "NetPnL": 0}

    df = df.copy()

    # 1. Sinyal Üretimi (Vektörel)
    df['Signal'] = 0
    if direction == "Long":
        df.loc[(df['Close'] > df['EMA_50']) & (df['RSI_14'] < 30) & (df['MACD_12_26_9'] > 0), 'Signal'] = 1
    elif direction == "Short":
        df.loc[(df['Close'] < df['EMA_50']) & (df['RSI_14'] > 70) & (df['MACD_12_26_9'] < 0), 'Signal'] = -1

    # İşleme Sinyalin geldiği ERTESİ mumda girilir (Shift 1)
    df['Position'] = df['Signal'].shift(1)

    trades = []
    in_position = False
    entry_price = 0
    sl = 0
    tp = 0

    # Not: Tam vektörel SL/TP takibi pandas'da zordur, bu yüzden sinyalleri
    # vektörel bulup, çıkışları iteratif yapıyoruz. (Hız için iterrows yerine apply/itertuples)
    for row in df.itertuples():
        if not in_position and row.Position != 0:
            # İşleme Giriş (Slippage Dahil)
            in_position = True
            if row.Position == 1: # Long
                entry_price = row.Open * (1 + slippage_pct)
                sl = entry_price - (sl_multiplier * row.ATRr_14)
                tp = entry_price + (tp_multiplier * row.ATRr_14)
            else: # Short
                entry_price = row.Open * (1 - slippage_pct)
                sl = entry_price + (sl_multiplier * row.ATRr_14)
                tp = entry_price - (tp_multiplier * row.ATRr_14)

            entry_time = row.Index
            continue

        if in_position:
            # Çıkış Kontrolü (Aynı mumda SL ve TP patlarsa en kötü senaryoyu, yani SL'yi kabul et - Quant Kuralı)
            hit_sl = False
            hit_tp = False
            exit_price = 0

            if row.Position == 1: # Long
                if row.Low <= sl: hit_sl = True
                if row.High >= tp: hit_tp = True
            else: # Short
                if row.High >= sl: hit_sl = True
                if row.Low <= tp: hit_tp = True

            if hit_sl and hit_tp:
                hit_tp = False # Aynı mumda ikisi de değdiyse Zarar yaz (Conservative Approach)

            if hit_sl:
                exit_price = sl * (1 - slippage_pct) if row.Position == 1 else sl * (1 + slippage_pct)
            elif hit_tp:
                exit_price = tp * (1 - slippage_pct) if row.Position == 1 else tp * (1 + slippage_pct)

            if hit_sl or hit_tp:
                # İşlem Kapandı
                pnl = (exit_price - entry_price) / entry_price if row.Position == 1 else (entry_price - exit_price) / entry_price
                trades.append({
                    "EntryTime": entry_time,
                    "ExitTime": row.Index,
                    "EntryPrice": entry_price,
                    "ExitPrice": exit_price,
                    "PnL_Pct": pnl * 100, # Yüzde
                    "Result": "Win" if pnl > 0 else "Loss"
                })
                in_position = False

    # 2. Raporlama Metrikleri (Tear Sheet Verileri)
    if not trades:
        return {"Trades": 0, "WinRate": 0, "ProfitFactor": 0, "NetPnL": 0}

    df_trades = pd.DataFrame(trades)
    wins = df_trades[df_trades['Result'] == 'Win']
    losses = df_trades[df_trades['Result'] == 'Loss']

    win_rate = len(wins) / len(df_trades) if len(df_trades) > 0 else 0

    gross_profit = wins['PnL_Pct'].sum() if not wins.empty else 0
    gross_loss = abs(losses['PnL_Pct'].sum()) if not losses.empty else 1 # Sıfıra bölme hatası önlemi

    profit_factor = gross_profit / gross_loss
    net_pnl = df_trades['PnL_Pct'].sum()

    # Max Drawdown (Kümülatif Getiri üzerinden)
    df_trades['CumPnL'] = df_trades['PnL_Pct'].cumsum()
    df_trades['Peak'] = df_trades['CumPnL'].cummax()
    df_trades['Drawdown'] = df_trades['Peak'] - df_trades['CumPnL']
    max_dd = df_trades['Drawdown'].max()

    return {
        "Trades": len(df_trades),
        "WinRate": win_rate * 100,
        "ProfitFactor": profit_factor,
        "NetPnL": net_pnl,
        "MaxDrawdown": max_dd
    }

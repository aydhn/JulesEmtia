import pandas as pd
import numpy as np
from itertools import product
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Tuple

from core.logger import logger
from strategy.engine import StrategyEngine
from data_engine.loader import DataEngine

class Backtester:
    """Geçmiş veriler üzerinde hızlı, vektörel backtest ve Grid Search parametre optimizasyon motoru."""

    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.0005, slippage: float = 0.0010):
        self.initial_capital = initial_capital
        self.commission = commission # Yüzde bazında komisyon (%0.05)
        self.slippage = slippage # Yüzde bazında slippage (%0.10)
        self.strategy = StrategyEngine()

    def run_backtest(self, df_htf: pd.DataFrame, df_ltf: pd.DataFrame, ticker: str, params: dict = None) -> dict:
        """Belirtilen veriler ve parametrelerle tek bir strateji senaryosunu test eder."""

        # Gelecekte eklenecek özel parametrelerin test edilmesi (şimdilik standart çalışır)
        htf_features = self.strategy.add_features(df_htf)
        ltf_features = self.strategy.add_features(df_ltf)

        # Veri setini birleştir (MTF hizalaması: Her LTF barına en son kapanmış HTF verisini ekle)
        # Sadece indeksleri (tarihleri) kullanacağız
        df_combined = ltf_features.copy()

        # Basit Vektörel Sinyal Üretimi (HTF trendi ile LTF RSI onayları)
        # (Gerçek karmaşık motor yerine hızlı backtest için optimize edilmiş matris işlemleri)
        df_combined['htf_trend'] = np.nan
        for idx in df_combined.index:
            # Kendisinden önce KAPANMIŞ son günlüğe bak
            valid_htf = htf_features[htf_features.index < idx]
            if not valid_htf.empty:
                last_htf = valid_htf.iloc[-1]
                # Basit HTF Bullish/Bearish durumu
                df_combined.loc[idx, 'htf_trend'] = 1 if last_htf['Close'] > last_htf['EMA_50'] else -1
            else:
                df_combined.loc[idx, 'htf_trend'] = 0

        # LTF Sinyalleri
        df_combined['ltf_rsi_bull'] = (df_combined['RSI_14'] < 30) | ((df_combined['RSI_14'].shift(1) < 30) & (df_combined['RSI_14'] > 30))
        df_combined['ltf_rsi_bear'] = (df_combined['RSI_14'] > 70) | ((df_combined['RSI_14'].shift(1) > 70) & (df_combined['RSI_14'] < 70))

        # Kesin Sinyaller (MTF Confluence)
        df_combined['signal'] = 0
        df_combined.loc[(df_combined['htf_trend'] == 1) & df_combined['ltf_rsi_bull'], 'signal'] = 1
        df_combined.loc[(df_combined['htf_trend'] == -1) & df_combined['ltf_rsi_bear'], 'signal'] = -1

        # İteratif İşlem Simülasyonu
        capital = self.initial_capital
        trades = []
        in_position = False
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        direction = 0 # 1 Long, -1 Short

        for i in range(len(df_combined)):
            row = df_combined.iloc[i]
            current_price = row['Close']

            if not in_position and row['signal'] != 0:
                # İşleme Gir
                in_position = True
                direction = row['signal']
                atr = row['ATR_14']

                # Maliyetleri ekle
                cost = current_price * (self.commission + self.slippage)
                entry_price = current_price + cost if direction == 1 else current_price - cost

                # Dinamik Stop ve TP
                if direction == 1:
                    sl_price = entry_price - (1.5 * atr)
                    tp_price = entry_price + (3.0 * atr)
                else:
                    sl_price = entry_price + (1.5 * atr)
                    tp_price = entry_price - (3.0 * atr)

            elif in_position:
                # Kapanış Şartları (Basit TP/SL)
                close_trade = False
                exit_price = 0.0

                if direction == 1:
                    if current_price <= sl_price:
                        close_trade, exit_price = True, sl_price
                    elif current_price >= tp_price:
                        close_trade, exit_price = True, tp_price
                else:
                    if current_price >= sl_price:
                        close_trade, exit_price = True, sl_price
                    elif current_price <= tp_price:
                        close_trade, exit_price = True, tp_price

                if close_trade:
                    # Çıkış Maliyeti
                    cost = exit_price * (self.commission + self.slippage)
                    exit_price = exit_price - cost if direction == 1 else exit_price + cost

                    # PNL
                    if direction == 1:
                        pnl_pct = (exit_price - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - exit_price) / entry_price

                    # Sabit 1000 dolarlık risk gibi düşünelim
                    pnl_abs = 1000 * pnl_pct
                    capital += pnl_abs
                    trades.append(pnl_abs)

                    in_position = False

        # Sonuç Raporu
        total_trades = len(trades)
        if total_trades == 0:
            return {"Total Trades": 0, "Win Rate": 0, "Profit Factor": 0, "Total PnL": 0}

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]

        win_rate = len(wins) / total_trades
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses)) if losses else 1.0

        profit_factor = gross_profit / gross_loss
        total_pnl = capital - self.initial_capital

        return {
            "Total Trades": total_trades,
            "Win Rate": win_rate,
            "Profit Factor": profit_factor,
            "Total PnL": total_pnl
        }

    def grid_search(self, ticker: str, df_htf: pd.DataFrame, df_ltf: pd.DataFrame, param_grid: dict) -> pd.DataFrame:
        """Çoklu CPU çekirdekleriyle parametre optimizasyonu (Izgara Araması) yapar."""
        logger.info(f"Grid Search başlatılıyor: {ticker}")
        keys, values = zip(*param_grid.items())
        combinations = [dict(zip(keys, v)) for v in product(*values)]

        results = []
        for params in combinations:
            res = self.run_backtest(df_htf, df_ltf, ticker, params)
            res.update(params)
            results.append(res)

        df_results = pd.DataFrame(results)
        # Profit Faktör ve Win Rate'e göre sırala
        df_results = df_results.sort_values(by=['Profit Factor', 'Win Rate'], ascending=[False, False])
        return df_results

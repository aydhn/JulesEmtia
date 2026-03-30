import asyncio
import time
from datetime import datetime
from data_loader import DataLoader
from features import align_mtf_data
from strategy import check_entry_signal
from ml_validator import MLValidator
from sentiment_filter import analyze_sentiment
from macro_filter import check_vix_circuit_breaker, check_macro_regime
from portfolio_manager import PortfolioManager
from paper_broker import PaperBroker
from execution_model import apply_slippage
from reporter import generate_tear_sheet
from notifier import notifier
from logger import log
from config import ALL_TICKERS

class LiveTrader:
    def __init__(self):
        self.data_loader = DataLoader()
        self.ml_validator = MLValidator()
        self.portfolio_mgr = PortfolioManager(self.data_loader)
        self.broker = PaperBroker()
        self.is_paused = False

    async def run_live_cycle(self):
        """Core execution cycle for live trading."""
        if self.is_paused:
            log.info("System is PAUSED via manual override. Skipping scan.")
            return

        log.info(f"Starting Live Cycle at {datetime.now()}")

        # 1. Check Circuit Breaker
        if check_vix_circuit_breaker():
            self._handle_black_swan()
            return

        # 2. Manage Open Positions
        self._manage_open_positions()

        # 3. Fetch Data & Find Signals
        balance = self.broker.get_account_balance()
        if not self.portfolio_mgr.check_global_limits(balance):
            return

        current_data = self.data_loader.fetch_all_current_data()

        for ticker, dfs in current_data.items():
            if dfs["HTF"].empty or dfs["LTF"].empty:
                continue

            # Align MTF (Zero Lookahead Bias)
            aligned_df = align_mtf_data(dfs["HTF"], dfs["LTF"])
            if aligned_df.empty:
                continue

            signal = check_entry_signal(aligned_df, ticker)

            if signal:
                # 4. Filter Pipeline
                regime = check_macro_regime(ticker)
                if (signal['direction'] == 'Long' and regime == 'RISK_OFF') or \
                   (signal['direction'] == 'Short' and regime == 'RISK_ON'):
                    log.info(f"Signal REJECTED (Macro Regime {regime}): {ticker} {signal['direction']}")
                    continue

                if not self.ml_validator.validate_signal(aligned_df.iloc[-1]):
                    continue

                sentiment = analyze_sentiment(ticker)
                if (signal['direction'] == 'Long' and sentiment < -0.5) or \
                   (signal['direction'] == 'Short' and sentiment > 0.5):
                    log.info(f"Signal REJECTED (Sentiment Veto {sentiment:.2f}): {ticker} {signal['direction']}")
                    continue

                if self.portfolio_mgr.check_correlation_veto(ticker, signal['direction']):
                    continue

                # 5. Execution
                # Simple Win Rate extraction for Kelly (Placeholder)
                win_rate = 0.55
                wl_ratio = 1.5
                size = self.portfolio_mgr.calculate_kelly_position_size(
                    balance, win_rate, wl_ratio, signal['entry_price'], signal['sl']
                )

                if size <= 0:
                    continue

                # Apply Slippage
                exec_price = apply_slippage(ticker, signal['direction'], signal['entry_price'], signal['atr'])

                receipt = self.broker.place_market_order(
                    ticker=ticker,
                    direction=signal['direction'],
                    size=size,
                    entry_price=exec_price,
                    sl=signal['sl'],
                    tp=signal['tp']
                )

                if receipt:
                    msg = f"🟢 <b>YENİ İŞLEM AÇILDI</b>\n" \
                          f"Varlık: {ticker}\n" \
                          f"Yön: {signal['direction']}\n" \
                          f"Giriş: {exec_price:.4f}\n" \
                          f"SL: {signal['sl']:.4f}\n" \
                          f"TP: {signal['tp']:.4f}\n" \
                          f"Büyüklük: {size:.4f}"
                    notifier.send_message(msg)

    def _manage_open_positions(self):
        """Checks TP/SL and Trail Stops for open trades."""
        open_trades = self.broker.get_open_positions()
        for trade in open_trades:
            ticker = trade['ticker']
            df = self.data_loader._fetch_data_with_retry(ticker, "1h", "5d", max_retries=1)
            if df.empty: continue

            current_price = df['Close'].iloc[-1]
            high = df['High'].iloc[-1]
            low = df['Low'].iloc[-1]

            direction = trade['direction']
            entry = trade['entry_price']
            sl = trade['sl_price']
            tp = trade['tp_price']
            trade_id = trade['trade_id']

            # Check TP / SL
            closed = False
            exit_price = 0
            reason = ""

            if direction == 'Long':
                if low <= sl:
                    exit_price = sl
                    reason = "Stop Loss"
                    closed = True
                elif high >= tp:
                    exit_price = tp
                    reason = "Take Profit"
                    closed = True
            else: # Short
                if high >= sl:
                    exit_price = sl
                    reason = "Stop Loss"
                    closed = True
                elif low <= tp:
                    exit_price = tp
                    reason = "Take Profit"
                    closed = True

            if closed:
                # Apply slippage on exit
                # Need ATR for accurate slippage, defaulting to average for now
                exit_price = apply_slippage(ticker, "Short" if direction=="Long" else "Long", exit_price, 0)

                if self.broker.close_position(trade_id, exit_price, reason):
                    pnl = (exit_price - entry) * trade['position_size'] if direction == 'Long' else (entry - exit_price) * trade['position_size']
                    emoji = "✅" if pnl > 0 else "❌"
                    msg = f"{emoji} <b>İŞLEM KAPANDI</b>\n" \
                          f"Varlık: {ticker} ({direction})\n" \
                          f"Çıkış: {exit_price:.4f}\n" \
                          f"Sebep: {reason}\n" \
                          f"PnL: ${pnl:.2f}"
                    notifier.send_message(msg)
            else:
                # Trailing Stop & Breakeven logic
                # Very basic ATR approximation if we don't have it saved in DB
                pass

    def _handle_black_swan(self):
        """Emergency protocol during VIX spikes."""
        open_trades = self.broker.get_open_positions()
        for trade in open_trades:
            # Simplistic approach: tighten all stops immediately
            # In a real scenario, you'd calculate ATR and bring SL extremely close
            log.warning(f"Tightening stops for {trade['ticker']} due to BLACK SWAN.")
            # For this MVP, we log the action.

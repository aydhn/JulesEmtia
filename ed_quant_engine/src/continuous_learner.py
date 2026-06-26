from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces
from rich.console import Console
from rich.table import Table
from stable_baselines3 import PPO

from src.backtester import run_vectorized_backtest
from src.config import (
    ALL_TICKERS,
    PPO_BOOTSTRAP_TIMESTEPS,
    PPO_MIN_ROWS,
    PPO_ROUTINE_TIMESTEPS,
    TRAINING_BOOTSTRAP_SLEEP_SECONDS,
    TRAINING_ROUTINE_SLEEP_SECONDS,
)
from src.data_loader import fetch_ticker_data_async
from src.features import add_features
from src.logger import get_logger
from src.paths import MODEL_DIR, MODEL_QUARANTINE_DIR, model_file


logger = get_logger()
console = Console()
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FEATURES = ["RSI_14", "ATR_14", "Log_Ret", "MFI_14", "CMF_20", "ATR_PCT"]
BOOTSTRAP_COVERAGE_THRESHOLD = 0.5
BOOTSTRAP_WINRATE_THRESHOLD = 60.0
PPO_SCHEMA_VERSION = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ppo_paths(ticker: str) -> tuple[Path, Path]:
    return model_file(ticker, "ppo.zip"), model_file(ticker, "ppo.json")


def _quarantine(path: Path, reason: str) -> None:
    if not path.exists():
        return
    target = MODEL_QUARANTINE_DIR / f"{path.stem}.{reason}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{path.suffix}"
    shutil.move(str(path), str(target))
    logger.warning("Quarantined model %s -> %s", path, target)


class TradingEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000.0):
        super().__init__()
        missing = [col for col in MODEL_FEATURES if col not in df.columns]
        if missing:
            raise ValueError(f"missing PPO features: {missing}")

        clean = df.replace([np.inf, -np.inf], np.nan).dropna(subset=MODEL_FEATURES + ["Close"]).copy()
        if len(clean) < PPO_MIN_ROWS:
            raise ValueError(f"insufficient rows ({len(clean)} < {PPO_MIN_ROWS})")

        self.data = clean[MODEL_FEATURES].values.astype(np.float32)
        self.close_prices = clean["Close"].values.astype(np.float32)
        self.initial_balance = initial_balance
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(len(MODEL_FEATURES),),
            dtype=np.float32,
        )
        self.current_step = 0
        self.position = 0
        self.entry_price = 0.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.position = 0
        self.entry_price = 0.0
        return self.data[0], {}

    def step(self, action):
        action_val = int(np.atleast_1d(np.asarray(action)).flat[0])
        reward = 0.0
        current_price = float(self.close_prices[self.current_step])

        if action_val == 1:
            if self.position == -1:
                reward += (self.entry_price - current_price) / max(self.entry_price, 1e-9)
            if self.position != 1:
                self.position = 1
                self.entry_price = current_price
        elif action_val == 2:
            if self.position == 1:
                reward += (current_price - self.entry_price) / max(self.entry_price, 1e-9)
            if self.position != -1:
                self.position = -1
                self.entry_price = current_price

        reward -= 0.0001
        self.current_step += 1
        max_step = len(self.data) - 1
        terminated = self.current_step >= max_step
        if terminated:
            final_price = float(self.close_prices[min(self.current_step, max_step)])
            if self.position == 1:
                reward += (final_price - self.entry_price) / max(self.entry_price, 1e-9)
            elif self.position == -1:
                reward += (self.entry_price - final_price) / max(self.entry_price, 1e-9)

        return self.data[min(self.current_step, max_step)], float(reward), terminated, False, {}


class ContinuousLearner:
    def __init__(self):
        self.performance_metrics: dict[str, dict] = {}
        self._cycle_count = 0

    async def fetch_and_prepare_data(self, ticker: str) -> pd.DataFrame:
        try:
            df = await fetch_ticker_data_async(ticker, period="max", interval="1d")
            return add_features(df, "1d") if not df.empty else pd.DataFrame()
        except Exception as exc:
            logger.error("Error preparing training data for %s: %s", ticker, exc)
            return pd.DataFrame()

    def _ppo_manifest_valid(self, manifest_path: Path, env: TradingEnv) -> bool:
        if not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return (
            manifest.get("schema_version") == PPO_SCHEMA_VERSION
            and manifest.get("features") == MODEL_FEATURES
            and tuple(manifest.get("observation_shape", [])) == env.observation_space.shape
        )

    def train_ppo(self, ticker: str, df: pd.DataFrame, bootstrap_mode: bool) -> tuple[bool, float, float]:
        model_path, manifest_path = _ppo_paths(ticker)
        total_timesteps = PPO_BOOTSTRAP_TIMESTEPS if bootstrap_mode else PPO_ROUTINE_TIMESTEPS

        try:
            env = TradingEnv(df)
        except ValueError as exc:
            logger.info("PPO deferred for %s: %s", ticker, exc)
            return False, 0.0, 0.0

        try:
            if model_path.exists() and self._ppo_manifest_valid(manifest_path, env):
                model = PPO.load(model_path, env=env)
                logger.info("PPO model loaded for %s.", ticker)
            else:
                _quarantine(model_path, "manifest_mismatch")
                _quarantine(manifest_path, "manifest_mismatch")
                model = PPO("MlpPolicy", env, verbose=0, n_steps=256, batch_size=64)

            model.learn(total_timesteps=total_timesteps, reset_num_timesteps=False)
            model.save(model_path)
            manifest = {
                "ticker": ticker,
                "model_type": "PPO",
                "schema_version": PPO_SCHEMA_VERSION,
                "trained_at": _utc_now(),
                "features": MODEL_FEATURES,
                "observation_shape": list(env.observation_space.shape),
                "timesteps": total_timesteps,
            }
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("PPO training failed for %s: %s", ticker, exc, exc_info=True)
            return False, 0.0, 0.0

        try:
            obs, _ = env.reset()
            total_reward = 0.0
            trades = 0
            wins = 0
            for _ in range(min(300, len(env.data) - 1)):
                action, _ = model.predict(obs, deterministic=True)
                action_val = int(np.atleast_1d(np.asarray(action)).flat[0])
                obs, reward, done, _, _ = env.step(action_val)
                total_reward += reward
                if action_val != 0:
                    trades += 1
                    wins += int(reward > 0)
                if done:
                    break
            win_rate = wins / trades * 100.0 if trades else 0.0
            return True, win_rate, total_reward * 100.0
        except Exception as exc:
            logger.error("PPO evaluation failed for %s: %s", ticker, exc)
            return True, 0.0, 0.0

    def train_rf(self, ticker: str, df: pd.DataFrame) -> tuple[bool, float]:
        from src.ml_validator import train_symbol_model

        return train_symbol_model(ticker, df)

    def run_backtest_for_ticker(self, ticker: str, df: pd.DataFrame) -> dict:
        try:
            result = run_vectorized_backtest(df, ticker)
            trades = result.get("trades", [])
            if not trades:
                return {}
            wins = [trade for trade in trades if trade["pnl"] > 0]
            gross_profit = sum(trade["pnl"] for trade in wins)
            gross_loss = abs(sum(trade["pnl"] for trade in trades if trade["pnl"] <= 0))
            return {
                "bt_trades": len(trades),
                "bt_win_rate": len(wins) / len(trades) * 100,
                "bt_profit_factor": gross_profit / gross_loss if gross_loss > 0 else 0.0,
                "bt_final_balance": result.get("final_balance", 10000.0),
            }
        except Exception as exc:
            logger.warning("Backtest failed for %s: %s", ticker, exc)
            return {}

    def display_summary_table(self) -> None:
        if not self.performance_metrics:
            return
        table = Table(title=f"ML training cycle #{self._cycle_count}", show_lines=True)
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Rows", justify="right")
        table.add_column("PPO WR", justify="right")
        table.add_column("RF OOS", justify="right")
        table.add_column("BT WR", justify="right")
        table.add_column("BT PF", justify="right")
        for ticker, metrics in self.performance_metrics.items():
            table.add_row(
                ticker,
                f"{metrics.get('samples', 0):,}",
                f"{metrics.get('ppo_win_rate', 0):.1f}%",
                f"{metrics.get('rf_win_rate', 0):.1f}%",
                f"{metrics.get('bt_win_rate', 0):.1f}%" if metrics.get("bt_win_rate") else "-",
                f"{metrics.get('bt_profit_factor', 0):.2f}" if metrics.get("bt_profit_factor") else "-",
            )
        try:
            console.print(table)
        except Exception:
            pass

    async def send_training_report(self, bootstrap_mode: bool) -> None:
        if not self.performance_metrics:
            return
        metrics = self.performance_metrics
        avg_ppo = sum(m.get("ppo_win_rate", 0) for m in metrics.values()) / len(metrics)
        avg_rf = sum(m.get("rf_win_rate", 0) for m in metrics.values()) / len(metrics)
        msg = (
            f"<b>ML training cycle #{self._cycle_count}</b>\n"
            f"Symbols trained: {len(metrics)}/{len(ALL_TICKERS)}\n"
            f"Avg PPO WR: {avg_ppo:.1f}%\n"
            f"Avg RF OOS: {avg_rf:.1f}%\n"
            f"Mode: {'bootstrap' if bootstrap_mode else 'routine'}"
        )
        try:
            from src.notifier import send_telegram_message

            await send_telegram_message(msg)
        except Exception:
            pass

    async def learning_loop(self) -> None:
        logger.info("Continuous learner started. model_dir=%s", MODEL_DIR)
        while True:
            self._cycle_count += 1
            trained = len(self.performance_metrics)
            avg_wr = (
                sum(m.get("ppo_win_rate", 0) for m in self.performance_metrics.values()) / max(trained, 1)
                if self.performance_metrics
                else 0.0
            )
            bootstrap_mode = trained < len(ALL_TICKERS) * BOOTSTRAP_COVERAGE_THRESHOLD or avg_wr < BOOTSTRAP_WINRATE_THRESHOLD
            cycle_metrics: dict[str, dict] = {}

            for ticker in ALL_TICKERS:
                df = await self.fetch_and_prepare_data(ticker)
                if df.empty:
                    logger.info("Training deferred for %s: no prepared data.", ticker)
                    continue
                ppo_ok, ppo_wr, ppo_pnl = await asyncio.to_thread(self.train_ppo, ticker, df, bootstrap_mode)
                rf_ok, rf_acc = await asyncio.to_thread(self.train_rf, ticker, df)
                bt_metrics = await asyncio.to_thread(self.run_backtest_for_ticker, ticker, df)
                cycle_metrics[ticker] = {
                    "ppo_win_rate": ppo_wr if ppo_ok else 0.0,
                    "expected_pnl": ppo_pnl,
                    "rf_win_rate": rf_acc if rf_ok else 0.0,
                    "samples": len(df),
                    **bt_metrics,
                }
                self.performance_metrics.update(cycle_metrics)
                await asyncio.sleep(0.1)

            self.performance_metrics.update(cycle_metrics)
            self.display_summary_table()
            await self.send_training_report(bootstrap_mode)

            trained = len(self.performance_metrics)
            avg_wr = sum(m.get("ppo_win_rate", 0) for m in self.performance_metrics.values()) / max(trained, 1)
            sleep_for = TRAINING_BOOTSTRAP_SLEEP_SECONDS if bootstrap_mode else TRAINING_ROUTINE_SLEEP_SECONDS
            logger.info(
                "Training cycle complete. trained=%s/%s avg_ppo_wr=%.1f%% sleep=%ss",
                trained,
                len(ALL_TICKERS),
                avg_wr,
                sleep_for,
            )
            await asyncio.sleep(sleep_for)


learner = ContinuousLearner()


async def start_continuous_learner() -> None:
    await learner.learning_loop()

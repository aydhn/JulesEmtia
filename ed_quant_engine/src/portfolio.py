from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    CORRELATION_THRESHOLD,
    MAX_GLOBAL_RISK_PCT,
    MAX_POSITIONS,
    MAX_SINGLE_RISK_CAP,
)
from src.logger import get_logger
import src.paper_db as db


logger = get_logger()


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    risk_pct: float
    total_open_risk_pct: float
    context: dict[str, Any] = field(default_factory=dict)


def _direction_sign(direction: str) -> int:
    return 1 if direction == "Long" else -1


def current_open_risk(balance: float | None = None) -> tuple[float, float]:
    balance = balance or db.get_balance()
    open_trades = db.get_open_trades()
    open_risk = sum(float(t.get("open_risk") or 0.0) for t in open_trades)
    return open_risk, open_risk / max(balance, 1e-12)


def check_global_limits(current_balance: float) -> bool:
    decision = evaluate_global_limits(current_balance)
    if not decision.approved:
        logger.info("Global limit veto: %s context=%s", decision.reason, decision.context)
    return decision.approved


def evaluate_global_limits(current_balance: float) -> RiskDecision:
    open_trades = db.get_open_trades()
    open_risk, open_risk_pct = current_open_risk(current_balance)

    if len(open_trades) >= MAX_POSITIONS:
        return RiskDecision(
            approved=False,
            reason="MAX_POSITIONS",
            risk_pct=0.0,
            total_open_risk_pct=open_risk_pct,
            context={"open_positions": len(open_trades), "limit": MAX_POSITIONS},
        )
    if open_risk_pct >= MAX_GLOBAL_RISK_PCT:
        return RiskDecision(
            approved=False,
            reason="MAX_GLOBAL_RISK",
            risk_pct=0.0,
            total_open_risk_pct=open_risk_pct,
            context={"open_risk": open_risk, "limit_pct": MAX_GLOBAL_RISK_PCT},
        )
    return RiskDecision(True, "OK", 0.0, open_risk_pct, {"open_positions": len(open_trades)})


def calculate_correlation_matrix(price_dict: dict[str, pd.Series]) -> pd.DataFrame:
    if not price_dict:
        return pd.DataFrame()
    df = pd.DataFrame(price_dict).dropna(how="all")
    if df.empty:
        return pd.DataFrame()
    returns = np.log(df / df.shift(1)).replace([np.inf, -np.inf], np.nan).dropna(how="all")
    if len(returns) < 20:
        return pd.DataFrame()
    return returns.tail(60).corr(method="pearson")


def check_correlation_veto(ticker: str, direction: str, corr_matrix: pd.DataFrame) -> bool:
    decision = evaluate_correlation_veto(ticker, direction, corr_matrix)
    if not decision.approved:
        logger.info("Correlation veto: %s context=%s", decision.reason, decision.context)
    return decision.approved


def evaluate_correlation_veto(ticker: str, direction: str, corr_matrix: pd.DataFrame) -> RiskDecision:
    open_trades = db.get_open_trades()
    if not open_trades:
        return RiskDecision(True, "OK", 0.0, current_open_risk()[1])

    for trade in open_trades:
        open_ticker = trade["ticker"]
        open_dir = trade["direction"]
        if ticker == open_ticker:
            return RiskDecision(
                False,
                "DUPLICATE_TICKER",
                0.0,
                current_open_risk()[1],
                {"ticker": ticker, "open_direction": open_dir},
            )
        if corr_matrix.empty or ticker not in corr_matrix.columns or open_ticker not in corr_matrix.columns:
            continue
        corr = float(corr_matrix.loc[ticker, open_ticker])
        if pd.isna(corr) or abs(corr) < CORRELATION_THRESHOLD:
            continue

        new_exposure = _direction_sign(direction)
        open_exposure = _direction_sign(open_dir)
        duplicated_risk = (corr > 0 and new_exposure == open_exposure) or (
            corr < 0 and new_exposure != open_exposure
        )
        if duplicated_risk:
            return RiskDecision(
                False,
                "CORRELATION_DUPLICATION",
                0.0,
                current_open_risk()[1],
                {
                    "ticker": ticker,
                    "direction": direction,
                    "open_ticker": open_ticker,
                    "open_direction": open_dir,
                    "correlation": corr,
                },
            )
    return RiskDecision(True, "OK", 0.0, current_open_risk()[1])


def evaluate_signal_risk(signal: dict[str, Any], corr_matrix: pd.DataFrame, current_balance: float) -> RiskDecision:
    global_decision = evaluate_global_limits(current_balance)
    if not global_decision.approved:
        return global_decision

    corr_decision = evaluate_correlation_veto(signal["ticker"], signal["direction"], corr_matrix)
    if not corr_decision.approved:
        return corr_decision

    risk_pct = float(signal.get("risk_pct") or calculate_fractional_kelly())
    risk_pct = max(0.005, min(risk_pct, MAX_SINGLE_RISK_CAP))
    _, open_risk_pct = current_open_risk(current_balance)
    projected = open_risk_pct + risk_pct
    if projected > MAX_GLOBAL_RISK_PCT:
        return RiskDecision(
            False,
            "PROJECTED_GLOBAL_RISK",
            risk_pct,
            open_risk_pct,
            {"projected_pct": projected, "limit_pct": MAX_GLOBAL_RISK_PCT},
        )
    return RiskDecision(True, "APPROVED", risk_pct, open_risk_pct, {"projected_pct": projected})


def calculate_fractional_kelly() -> float:
    df = db.get_closed_trades()
    if len(df) < 10:
        return 0.01

    winning = df[df["pnl"] > 0]
    losing = df[df["pnl"] <= 0]
    if winning.empty or losing.empty:
        return 0.01

    p = len(winning) / len(df)
    q = 1 - p
    avg_win = float(winning["pnl"].mean())
    avg_loss = abs(float(losing["pnl"].mean()))
    if avg_loss <= 0 or avg_win <= 0:
        return 0.01

    b = avg_win / avg_loss
    kelly = (b * p - q) / b
    half_kelly = kelly / 2.0
    return max(0.005, min(half_kelly, MAX_SINGLE_RISK_CAP))

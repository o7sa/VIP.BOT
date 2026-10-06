"""
Risk Manager - Protects capital while allowing aggressive scalping
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from config.settings import config
from strategies.scalping_strategy import Trade, TradeStatus

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    account_balance: float = 10000.0
    daily_pnl: float = 0.0
    daily_trades: int = 0
    open_risk: float = 0.0
    current_drawdown: float = 0.0
    peak_balance: float = 10000.0
    win_count: int = 0
    loss_count: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_balance": round(self.account_balance, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_trades": self.daily_trades,
            "open_risk": round(self.open_risk, 2),
            "current_drawdown": round(self.current_drawdown, 4),
            "peak_balance": round(self.peak_balance, 2),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_count / max(1, self.win_count + self.loss_count) * 100, 1),
            "total_profit": round(self.total_profit, 2),
            "total_loss": round(self.total_loss, 2),
            "profit_factor": round(self.total_profit / max(0.01, abs(self.total_loss)), 2)
        }


class RiskManager:
    def __init__(self):
        self.metrics = RiskMetrics()
        self.current_day = date.today()
        self.cfg = config.risk

    def _reset_daily(self):
        today = date.today()
        if today != self.current_day:
            self.metrics.daily_pnl = 0.0
            self.metrics.daily_trades = 0
            self.current_day = today
            logger.info("Risk manager daily reset")

    def record_trade(self, trade: Trade):
        self._reset_daily()
        if trade.status != TradeStatus.CLOSED or trade.profit is None:
            return
        self.metrics.daily_trades += 1
        self.metrics.daily_pnl += trade.profit
        self.metrics.account_balance += trade.profit
        if trade.profit >= 0:
            self.metrics.win_count += 1
            self.metrics.total_profit += trade.profit
        else:
            self.metrics.loss_count += 1
            self.metrics.total_loss += abs(trade.profit)
        if self.metrics.account_balance > self.metrics.peak_balance:
            self.metrics.peak_balance = self.metrics.account_balance
        dd = (self.metrics.peak_balance - self.metrics.account_balance) / self.metrics.peak_balance
        self.metrics.current_drawdown = max(0.0, dd)

    def update_open_trades(self, open_trades: List[Trade]):
        risk = 0.0
        for t in open_trades:
            if t.direction.value == "BUY":
                risk += abs(t.entry_price - t.stop_loss) * t.lot_size * 100
            else:
                risk += abs(t.stop_loss - t.entry_price) * t.lot_size * 100
        self.metrics.open_risk = risk

    def should_stop_trading(self) -> Tuple[bool, str]:
        self._reset_daily()
        if self.metrics.current_drawdown >= self.cfg.STOP_TRADING_AT_DRAWDOWN:
            return True, f"Drawdown limit hit: {self.metrics.current_drawdown*100:.1f}%"
        if self.metrics.daily_pnl <= -self.cfg.MAX_DAILY_LOSS * self.metrics.account_balance:
            return True, f"Daily loss limit hit: {self.metrics.daily_pnl:.2f}"
        if self.metrics.daily_pnl >= self.cfg.MAX_DAILY_PROFIT * self.metrics.account_balance:
            return True, f"Daily profit target reached: {self.metrics.daily_pnl:.2f}"
        return False, ""

    def can_open_trade(self, open_count: int) -> Tuple[bool, str]:
        if open_count >= self.cfg.MAX_OPEN_TRADES:
            return False, "Max open trades reached"
        stop, reason = self.should_stop_trading()
        if stop:
            return False, reason
        return True, "OK"

    def get_risk_report(self) -> Dict[str, Any]:
        stop, reason = self.should_stop_trading()
        level = "LOW"
        if self.metrics.current_drawdown > 0.08 or self.metrics.daily_pnl < -200:
            level = "MEDIUM"
        if self.metrics.current_drawdown > 0.12 or self.metrics.daily_pnl < -500:
            level = "HIGH"
        return {
            "risk_level": level,
            "should_stop_trading": stop,
            "stop_reason": reason,
            "metrics": self.metrics.to_dict()
        }


risk_manager = RiskManager()

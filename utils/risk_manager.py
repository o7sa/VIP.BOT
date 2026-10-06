"""
Risk Management Module - Comprehensive risk management for XAUUSD trading
"""

import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from config.settings import config
from strategies.scalping_strategy import Trade, TradeDirection, TradeStatus

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskAlert:
    """Represents a risk alert"""
    alert_id: str
    timestamp: datetime
    risk_level: RiskLevel
    alert_type: str
    message: str
    trade_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "risk_level": self.risk_level.value,
            "alert_type": self.alert_type,
            "message": self.message,
            "trade_id": self.trade_id
        }


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    account_balance: float = 10000.0  # Default starting balance
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    daily_profit: float = 0.0
    daily_loss: float = 0.0
    open_trades: int = 0
    max_open_trades: int = config.risk.MAX_OPEN_TRADES
    risk_per_trade: float = config.risk.MAX_TRADE_RISK_PERCENT
    total_exposure: float = 0.0
    max_exposure: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_balance": self.account_balance,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "daily_profit": self.daily_profit,
            "daily_loss": self.daily_loss,
            "open_trades": self.open_trades,
            "max_open_trades": self.max_open_trades,
            "risk_per_trade": self.risk_per_trade,
            "total_exposure": self.total_exposure,
            "max_exposure": self.max_exposure
        }


class RiskManager:
    """Comprehensive Risk Manager for XAUUSD Trading"""
    
    def __init__(self):
        self.account_balance = config.risk.ACCOUNT_BALANCE if hasattr(config.risk, 'ACCOUNT_BALANCE') else 10000.0
        self.initial_balance = self.account_balance
        self.risk_metrics = RiskMetrics(account_balance=self.account_balance)
        self.alerts: List[RiskAlert] = []
        self.alert_counter = 0
        
        # Track daily metrics
        self.daily_start_balance = self.account_balance
        self.trade_history: List[Trade] = []
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID"""
        self.alert_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"ALERT_{timestamp}_{self.alert_counter}"
    
    def update_balance(self, amount: float) -> float:
        """Update account balance"""
        self.account_balance += amount
        self.risk_metrics.account_balance = self.account_balance
        
        # Update drawdown
        drawdown = (self.initial_balance - self.account_balance) / self.initial_balance * 100
        self.risk_metrics.current_drawdown = abs(drawdown)
        self.risk_metrics.max_drawdown = max(self.risk_metrics.max_drawdown, self.risk_metrics.current_drawdown)
        
        return self.account_balance
    
    def record_trade(self, trade: Trade) -> None:
        """Record a trade for risk tracking"""
        self.trade_history.append(trade)
        
        if trade.status == TradeStatus.CLOSED and trade.profit is not None:
            if trade.profit > 0:
                self.risk_metrics.daily_profit += trade.profit
            else:
                self.risk_metrics.daily_loss += abs(trade.profit)
    
    def update_open_trades(self, open_trades: List[Trade]) -> None:
        """Update the list of open trades"""
        self.risk_metrics.open_trades = len(open_trades)
        
        # Calculate total exposure
        total_exposure = 0.0
        for trade in open_trades:
            # Estimate exposure based on lot size and price
            # For XAUUSD, 1 lot = 100 oz, 1 pip = 0.01
            pip_value = 0.01
            exposure_per_lot = trade.entry_price * 100 * pip_value
            total_exposure += exposure_per_lot * trade.lot_size
        
        self.risk_metrics.total_exposure = total_exposure
        self.risk_metrics.max_exposure = max(self.risk_metrics.max_exposure, total_exposure)
    
    def check_trade_risk(self, trade: Trade) -> Tuple[bool, Optional[str]]:
        """Check if a trade exceeds risk limits"""
        # Check position size
        max_risk_amount = self.account_balance * config.risk.MAX_TRADE_RISK_PERCENT
        
        # Estimate risk per trade
        if trade.direction == TradeDirection.BUY:
            risk_distance = trade.entry_price - trade.stop_loss
        else:
            risk_distance = trade.stop_loss - trade.entry_price
        
        # Risk in USD
        pip_value = 0.01
        risk_per_pip = trade.lot_size * 100000 * pip_value
        risk_amount = risk_distance * 100 * risk_per_pip  # Convert to USD
        
        if risk_amount > max_risk_amount:
            return False, f"Trade risk ({risk_amount:.2f}) exceeds max per trade ({max_risk_amount:.2f})"
        
        # Check daily loss limit
        if abs(self.risk_metrics.daily_loss) >= config.risk.MAX_DAILY_LOSS * self.account_balance:
            return False, f"Daily loss limit reached"
        
        # Check max open trades
        if self.risk_metrics.open_trades >= config.risk.MAX_OPEN_TRADES:
            return False, f"Max open trades reached"
        
        # Check total exposure
        total_exposure = self.risk_metrics.total_exposure + risk_amount
        if total_exposure > self.account_balance * 0.5:  # Max 50% exposure
            return False, f"Total exposure would exceed 50%"
        
        return True, None
    
    def check_system_risk(self) -> Tuple[RiskLevel, List[str]]:
        """Check overall system risk level"""
        issues = []
        risk_level = RiskLevel.LOW
        
        # Check drawdown
        if self.risk_metrics.current_drawdown >= config.risk.STOP_TRADING_AT_DRAWDOWN * 100:
            issues.append(f"Critical drawdown: {self.risk_metrics.current_drawdown:.2f}%")
            risk_level = RiskLevel.CRITICAL
        elif self.risk_metrics.current_drawdown >= config.risk.STOP_TRADING_AT_DRAWDOWN * 100 * 0.8:
            issues.append(f"High drawdown: {self.risk_metrics.current_drawdown:.2f}%")
            risk_level = RiskLevel.HIGH
        
        # Check daily loss
        daily_loss_percent = (self.risk_metrics.daily_loss / self.account_balance) * 100
        if daily_loss_percent >= config.risk.MAX_DAILY_LOSS * 100:
            issues.append(f"Daily loss limit reached: {daily_loss_percent:.2f}%")
            risk_level = RiskLevel.CRITICAL
        elif daily_loss_percent >= config.risk.MAX_DAILY_LOSS * 100 * 0.8:
            issues.append(f"Approaching daily loss limit: {daily_loss_percent:.2f}%")
            risk_level = RiskLevel.HIGH
        
        # Check max drawdown
        if self.risk_metrics.max_drawdown >= config.risk.MAX_DRAWDOWN * 100:
            issues.append(f"Max drawdown exceeded: {self.risk_metrics.max_drawdown:.2f}%")
            risk_level = RiskLevel.CRITICAL
        
        # Check open trades
        if self.risk_metrics.open_trades >= config.risk.MAX_OPEN_TRADES:
            issues.append(f"Max open trades: {self.risk_metrics.open_trades}")
            risk_level = max(risk_level, RiskLevel.MEDIUM)
        
        # Check exposure
        exposure_percent = (self.risk_metrics.total_exposure / self.account_balance) * 100
        if exposure_percent > 50:
            issues.append(f"High exposure: {exposure_percent:.2f}%")
            risk_level = max(risk_level, RiskLevel.HIGH)
        
        return risk_level, issues
    
    def should_stop_trading(self) -> Tuple[bool, Optional[str]]:
        """Check if trading should be stopped"""
        risk_level, issues = self.check_system_risk()
        
        if risk_level == RiskLevel.CRITICAL:
            return True, "; ".join(issues)
        
        # Check if we've hit daily trade limit
        if len([t for t in self.trade_history if t.entry_time.date() == datetime.utcnow().date()]) >= config.trading.DAILY_TRADES_LIMIT:
            return True, "Daily trade limit reached"
        
        return False, None
    
    def create_alert(
        self, 
        alert_type: str, 
        message: str, 
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        trade_id: Optional[str] = None
    ) -> RiskAlert:
        """Create a risk alert"""
        alert = RiskAlert(
            alert_id=self._generate_alert_id(),
            timestamp=datetime.utcnow(),
            risk_level=risk_level,
            alert_type=alert_type,
            message=message,
            trade_id=trade_id
        )
        
        self.alerts.append(alert)
        logger.warning(f"RISK ALERT [{risk_level.value}]: {message}")
        
        return alert
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Generate a comprehensive risk report"""
        risk_level, issues = self.check_system_risk()
        stop_trading, stop_reason = self.should_stop_trading()
        
        # Calculate statistics
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.profit is not None and t.profit > 0)
        losing_trades = sum(1 for t in self.trade_history if t.profit is not None and t.profit < 0)
        
        total_profit = sum(t.profit for t in self.trade_history if t.profit is not None and t.profit > 0)
        total_loss = sum(abs(t.profit) for t in self.trade_history if t.profit is not None and t.profit < 0)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        return {
            "risk_level": risk_level.value,
            "should_stop_trading": stop_trading,
            "stop_reason": stop_reason,
            "issues": issues,
            "metrics": self.risk_metrics.to_dict(),
            "statistics": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "total_loss": total_loss,
                "profit_factor": profit_factor,
                "account_growth": (self.account_balance - self.initial_balance) / self.initial_balance * 100
            },
            "alerts": [a.to_dict() for a in self.alerts[-10:]]  # Last 10 alerts
        }
    
    def reset_daily_metrics(self) -> None:
        """Reset daily metrics at the start of a new day"""
        self.daily_start_balance = self.account_balance
        self.risk_metrics.daily_profit = 0.0
        self.risk_metrics.daily_loss = 0.0


# Global instance
risk_manager = RiskManager()


if __name__ == "__main__":
    # Test the risk manager
    rm = RiskManager()
    
    print("Initial Risk Report:")
    report = rm.get_risk_report()
    for key, value in report.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")
    
    # Simulate some trades
    print("\n\nSimulating trades...")
    
    # Winning trade
    trade1 = Trade(
        trade_id="TEST_001",
        signal_id="SIG_001",
        direction=TradeDirection.BUY,
        entry_price=2000.0,
        entry_time=datetime.utcnow(),
        stop_loss=1990.0,
        take_profit=2020.0,
        lot_size=0.1,
        status=TradeStatus.CLOSED,
        exit_price=2020.0,
        exit_time=datetime.utcnow(),
        exit_reason="Take Profit"
    )
    trade1.profit, trade1.profit_percent = trade1.calculate_profit(2020.0)
    rm.record_trade(trade1)
    rm.update_balance(trade1.profit)
    
    # Losing trade
    trade2 = Trade(
        trade_id="TEST_002",
        signal_id="SIG_002",
        direction=TradeDirection.SELL,
        entry_price=2020.0,
        entry_time=datetime.utcnow(),
        stop_loss=2030.0,
        take_profit=2000.0,
        lot_size=0.1,
        status=TradeStatus.CLOSED,
        exit_price=2030.0,
        exit_time=datetime.utcnow(),
        exit_reason="Stop Loss"
    )
    trade2.profit, trade2.profit_percent = trade2.calculate_profit(2030.0)
    rm.record_trade(trade2)
    rm.update_balance(trade2.profit)
    
    print("\nUpdated Risk Report:")
    report = rm.get_risk_report()
    for key, value in report.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")

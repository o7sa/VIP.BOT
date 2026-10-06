"""
Aggressive Scalping Strategy for XAUUSD
High-frequency trading with 20 trades per day
"""

import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum

from modules.data_fetcher import Candle, MarketData, BIQuoteClient
from modules.technical_analyzer import (
    TechnicalAnalyzer, 
    AnalysisResult, 
    SignalType,
    TrendDirection
)
from modules.pattern_detector import PatternDetector, PatternType
from config.settings import config

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class TradeSignal:
    """Represents a trading signal"""
    signal_id: str
    timestamp: datetime
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-1
    strength: float  # 0-1
    
    # Signal reasoning
    reason: str
    indicators: Dict[str, float] = field(default_factory=dict)
    patterns: List[str] = field(default_factory=list)
    timeframe: str = "1m"
    
    # Risk management
    risk_percent: float = 0.02  # 2% per trade
    lot_size: float = 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "strength": self.strength,
            "reason": self.reason,
            "indicators": self.indicators,
            "patterns": self.patterns,
            "timeframe": self.timeframe,
            "risk_percent": self.risk_percent,
            "lot_size": self.lot_size
        }


@dataclass
class Trade:
    """Represents an executed trade"""
    trade_id: str
    signal_id: str
    direction: TradeDirection
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    lot_size: float
    
    # Exit info
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    
    # Performance
    profit: Optional[float] = None
    profit_percent: Optional[float] = None
    status: TradeStatus = TradeStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "trade_id": self.trade_id,
            "signal_id": self.signal_id,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "lot_size": self.lot_size,
            "status": self.status.value
        }
        
        if self.exit_price:
            result["exit_price"] = self.exit_price
        if self.exit_time:
            result["exit_time"] = self.exit_time.isoformat()
        if self.exit_reason:
            result["exit_reason"] = self.exit_reason
        if self.profit is not None:
            result["profit"] = self.profit
        if self.profit_percent is not None:
            result["profit_percent"] = self.profit_percent
        
        return result
    
    def calculate_profit(self, exit_price: float) -> Tuple[float, float]:
        """Calculate profit in points and percentage"""
        if self.direction == TradeDirection.BUY:
            profit_points = (exit_price - self.entry_price) * 100  # XAUUSD is typically quoted with 2 decimals
        else:
            profit_points = (self.entry_price - exit_price) * 100
        
        # For XAUUSD, 1 point = 0.01, so we need to adjust
        # Assuming standard lot size calculations
        pip_value = 0.01  # 1 pip = 0.01 for XAUUSD
        profit_usd = profit_points * pip_value * self.lot_size * 100000  # Standard lot is 100,000 units
        
        # Percentage based on margin (assuming 1:100 leverage)
        margin = self.entry_price * self.lot_size * 100000 / 100  # 1:100 leverage
        profit_percent = (profit_usd / margin) * 100 if margin > 0 else 0
        
        return profit_usd, profit_percent


@dataclass
class TradingSession:
    """Represents a trading session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    trades: List[Trade] = field(default_factory=list)
    signals_generated: int = 0
    signals_executed: int = 0
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "trades_count": len(self.trades),
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "total_profit": self.total_profit,
            "max_drawdown": self.max_drawdown
        }


class ScalpingStrategy:
    """Aggressive Scalping Strategy for XAUUSD"""
    
    def __init__(self):
        self.analyzer = TechnicalAnalyzer()
        self.pattern_detector = PatternDetector()
        self.trade_counter = 0
        self.daily_trades = 0
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.session_start: Optional[datetime] = None
        
        # Initialize new trading day
        self._initialize_day()
    
    def _initialize_day(self):
        """Initialize a new trading day"""
        today = datetime.utcnow().date()
        self.session_start = datetime(today.year, today.month, today.day, 0, 0, 0)
        self.daily_trades = 0
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.trade_counter = 0
    
    def _check_new_day(self) -> bool:
        """Check if it's a new trading day"""
        today = datetime.utcnow().date()
        session_date = self.session_start.date() if self.session_start else None
        
        if session_date != today:
            self._initialize_day()
            return True
        return False
    
    def _generate_signal_id(self) -> str:
        """Generate unique signal ID"""
        self.trade_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"SIG_{timestamp}_{self.trade_counter}"
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"TRADE_{timestamp}_{self.trade_counter}"
    
    def _can_trade(self) -> bool:
        """Check if we can open a new trade"""
        self._check_new_day()
        
        # Check daily limit
        if self.daily_trades >= config.trading.DAILY_TRADES_LIMIT:
            logger.info(f"Daily trade limit reached ({self.daily_trades}/{config.trading.DAILY_TRADES_LIMIT})")
            return False
        
        # Check max open trades
        if len(self.open_trades) >= config.risk.MAX_OPEN_TRADES:
            logger.info(f"Max open trades reached ({len(self.open_trades)}/{config.risk.MAX_OPEN_TRADES})")
            return False
        
        # Check daily loss limit
        if abs(self.daily_loss) >= config.risk.MAX_DAILY_LOSS:
            logger.warning(f"Daily loss limit reached ({self.daily_loss:.2f})")
            return False
        
        return True
    
    def _calculate_stop_loss_take_profit(
        self, 
        entry_price: float, 
        direction: TradeDirection,
        atr: float = None
    ) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels"""
        if atr is None:
            atr = 50  # Default ATR value for XAUUSD
        
        # Use ATR-based stop loss
        stop_distance = atr * 1.5
        take_profit_distance = atr * 3.0  # 1:3 risk-reward ratio
        
        if direction == TradeDirection.BUY:
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + take_profit_distance
        else:  # SELL
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - take_profit_distance
        
        return stop_loss, take_profit
    
    def _evaluate_signal_strength(
        self, 
        analysis: AnalysisResult,
        patterns: Dict[PatternType, List[Any]]
    ) -> Tuple[bool, float, str]:
        """Evaluate if we should generate a signal and its strength"""
        signal = analysis.overall_signal
        confidence = analysis.signal_confidence
        strength = analysis.signal_strength
        
        # Minimum requirements
        if confidence < config.signal.SIGNAL_CONFIDENCE_THRESHOLD:
            return False, 0.0, "Low confidence"
        
        if strength < config.signal.MIN_SIGNAL_STRENGTH:
            return False, 0.0, "Low strength"
        
        # Check for confirmation across multiple timeframes
        if config.signal.CONFIRMATION_REQUIRED:
            # This would be checked in the main analysis loop
            pass
        
        # Boost strength based on patterns
        pattern_boost = 0.0
        pattern_reasons = []
        
        # Check for strong patterns
        strong_patterns = [
            PatternType.HEAD_AND_SHOULDERS,
            PatternType.INVERSE_HEAD_AND_SHOULDERS,
            PatternType.DOUBLE_TOP,
            PatternType.DOUBLE_BOTTOM,
            PatternType.TRIPLE_TOP,
            PatternType.TRIPLE_BOTTOM,
            PatternType.TRENDLINE_BREAK,
            PatternType.BREAKOUT_UP,
            PatternType.BREAKOUT_DOWN
        ]
        
        for pattern_type in strong_patterns:
            if pattern_type in patterns and patterns[pattern_type]:
                latest_pattern = patterns[pattern_type][0]
                pattern_boost += latest_pattern.strength * 0.2
                pattern_reasons.append(latest_pattern.name)
        
        # Check for volume confirmation
        if analysis.volume_spike:
            pattern_boost += 0.15
            pattern_reasons.append("Volume Spike")
        
        # Check for breakouts
        if analysis.breakout_upper or analysis.breakout_lower:
            pattern_boost += 0.2
            pattern_reasons.append("Breakout")
        
        # Check for trend confirmation
        if (analysis.short_term_trend and analysis.medium_term_trend and
            analysis.short_term_trend.direction == analysis.medium_term_trend.direction):
            pattern_boost += 0.1
            pattern_reasons.append("Trend Confirmation")
        
        total_strength = min(strength + pattern_boost, 1.0)
        
        # Build reason
        signal_word = signal.value.replace("_", " ")
        reason = f"{signal_word} signal"
        if pattern_reasons:
            reason += f" with {', '.join(pattern_reasons)}"
        
        # Only generate signal for BUY or SELL (not NEUTRAL or WEAK)
        if signal in [SignalType.STRONG_BUY, SignalType.BUY, 
                      SignalType.STRONG_SELL, SignalType.SELL]:
            return True, total_strength, reason
        
        return False, 0.0, "Neutral signal"
    
    def _generate_signal(
        self, 
        analysis: AnalysisResult,
        patterns: Dict[PatternType, List[Any]],
        current_price: float
    ) -> Optional[TradeSignal]:
        """Generate a trading signal based on analysis"""
        should_trade, strength, reason = self._evaluate_signal_strength(analysis, patterns)
        
        if not should_trade:
            return None
        
        # Determine direction
        signal_type = analysis.overall_signal
        if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
            direction = TradeDirection.BUY
        elif signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
            direction = TradeDirection.SELL
        else:
            return None
        
        # Get ATR for stop loss calculation
        atr = None
        if "ATR" in analysis.indicators:
            atr = analysis.indicators["ATR"].value
        
        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_stop_loss_take_profit(
            current_price, direction, atr
        )
        
        # Adjust based on signal strength
        if strength > 0.8:
            # Strong signal - wider take profit
            if direction == TradeDirection.BUY:
                take_profit = current_price + (take_profit - current_price) * 1.5
            else:
                take_profit = current_price - (current_price - take_profit) * 1.5
        
        # Collect indicator values
        indicators = {}
        for name, value in analysis.indicators.items():
            if name in ["RSI", "MACD", "MACD_Signal", "MACD_Histogram", 
                       "Stochastic_K", "Stochastic_D", "ATR"]:
                indicators[name] = value.value
        
        # Collect pattern names
        pattern_names = []
        for pattern_type, pattern_list in patterns.items():
            if pattern_list:
                pattern_names.append(pattern_list[0].name)
        
        # Create signal
        signal = TradeSignal(
            signal_id=self._generate_signal_id(),
            timestamp=datetime.utcnow(),
            direction=direction,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=analysis.signal_confidence,
            strength=strength,
            reason=reason,
            indicators=indicators,
            patterns=pattern_names,
            timeframe=analysis.timeframe,
            risk_percent=config.risk.MAX_TRADE_RISK_PERCENT,
            lot_size=config.trading.LOT_SIZE
        )
        
        return signal
    
    def _execute_signal(self, signal: TradeSignal) -> Optional[Trade]:
        """Execute a trading signal"""
        if not self._can_trade():
            logger.info(f"Cannot execute signal {signal.signal_id}: trading limits reached")
            return None
        
        # Create trade
        trade = Trade(
            trade_id=self._generate_trade_id(),
            signal_id=signal.signal_id,
            direction=signal.direction,
            entry_price=signal.entry_price,
            entry_time=datetime.utcnow(),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            lot_size=signal.lot_size,
            status=TradeStatus.OPEN
        )
        
        self.open_trades.append(trade)
        self.daily_trades += 1
        
        logger.info(f"Executed trade {trade.trade_id}: {signal.direction.value} at {signal.entry_price}")
        
        return trade
    
    def _check_trade_exit(self, trade: Trade, current_price: float) -> bool:
        """Check if a trade should be exited"""
        if trade.status != TradeStatus.OPEN:
            return False
        
        # Check stop loss
        if (trade.direction == TradeDirection.BUY and current_price <= trade.stop_loss) or \
           (trade.direction == TradeDirection.SELL and current_price >= trade.stop_loss):
            trade.exit_price = current_price
            trade.exit_time = datetime.utcnow()
            trade.exit_reason = "Stop Loss"
            trade.profit, trade.profit_percent = trade.calculate_profit(current_price)
            trade.status = TradeStatus.CLOSED
            
            self.daily_loss += trade.profit if trade.profit < 0 else 0
            self.daily_profit += trade.profit if trade.profit > 0 else 0
            
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            
            logger.info(f"Trade {trade.trade_id} exited at SL: {current_price}, P&L: {trade.profit:.2f}")
            return True
        
        # Check take profit
        if (trade.direction == TradeDirection.BUY and current_price >= trade.take_profit) or \
           (trade.direction == TradeDirection.SELL and current_price <= trade.take_profit):
            trade.exit_price = current_price
            trade.exit_time = datetime.utcnow()
            trade.exit_reason = "Take Profit"
            trade.profit, trade.profit_percent = trade.calculate_profit(current_price)
            trade.status = TradeStatus.CLOSED
            
            self.daily_profit += trade.profit
            
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            
            logger.info(f"Trade {trade.trade_id} exited at TP: {current_price}, P&L: {trade.profit:.2f}")
            return True
        
        return False
    
    def _check_trailing_stop(self, trade: Trade, current_price: float) -> bool:
        """Check and update trailing stop"""
        if not config.trading.TRAILING_STOP:
            return False
        
        if trade.direction == TradeDirection.BUY:
            # Update trailing stop if price moves up
            if current_price > trade.entry_price + config.trading.TRAILING_STOP_DISTANCE:
                new_stop = current_price - config.trading.TRAILING_STOP_DISTANCE
                if new_stop > trade.stop_loss:
                    trade.stop_loss = new_stop
                    logger.debug(f"Trailing stop updated for {trade.trade_id}: {new_stop}")
        
        elif trade.direction == TradeDirection.SELL:
            # Update trailing stop if price moves down
            if current_price < trade.entry_price - config.trading.TRAILING_STOP_DISTANCE:
                new_stop = current_price + config.trading.TRAILING_STOP_DISTANCE
                if new_stop < trade.stop_loss:
                    trade.stop_loss = new_stop
                    logger.debug(f"Trailing stop updated for {trade.trade_id}: {new_stop}")
        
        return False
    
    async def analyze_and_trade(
        self, 
        candles: List[Candle], 
        current_price: MarketData
    ) -> Tuple[Optional[TradeSignal], List[Trade]]:
        """Analyze market and generate trades"""
        signals = []
        executed_trades = []
        
        # Analyze current market
        analysis = self.analyzer.analyze(candles, "1m")
        
        # Detect patterns
        patterns = self.pattern_detector.detect_all_patterns(candles)
        
        # Generate signal
        signal = self._generate_signal(analysis, patterns, current_price.bid)
        
        if signal:
            signals.append(signal)
            
            # Execute signal
            trade = self._execute_signal(signal)
            if trade:
                executed_trades.append(trade)
        
        # Check existing trades for exit
        closed_trades = []
        for trade in self.open_trades[:]:  # Iterate over a copy
            if self._check_trade_exit(trade, current_price.bid):
                closed_trades.append(trade)
            else:
                self._check_trailing_stop(trade, current_price.bid)
        
        return signal, executed_trades + closed_trades
    
    async def run_scalping_cycle(
        self, 
        client: BIQuoteClient
    ) -> Dict[str, Any]:
        """Run a complete scalping cycle"""
        try:
            # Fetch data
            candles = await client.get_historical_candles("1m", 200)
            current_price = await client.get_current_price()
            
            if not candles or len(candles) < 50:
                return {"status": "error", "message": "Insufficient data"}
            
            # Analyze and trade
            signal, trades = await self.analyze_and_trade(candles, current_price)
            
            result = {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "current_price": current_price.bid,
                "trades_executed": len([t for t in trades if t.status == TradeStatus.OPEN]),
                "trades_closed": len([t for t in trades if t.status == TradeStatus.CLOSED]),
                "daily_trades": self.daily_trades,
                "daily_profit": self.daily_profit,
                "open_trades": len(self.open_trades),
                "signal": signal.to_dict() if signal else None
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Scalping cycle failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_trade_summary(self) -> Dict[str, Any]:
        """Get summary of current trading session"""
        total_profit = sum(t.profit for t in self.closed_trades if t.profit is not None)
        winning_trades = sum(1 for t in self.closed_trades if t.profit is not None and t.profit > 0)
        losing_trades = sum(1 for t in self.closed_trades if t.profit is not None and t.profit < 0)
        
        return {
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "daily_trades": self.daily_trades,
            "max_daily_trades": config.trading.DAILY_TRADES_LIMIT,
            "open_trades": len(self.open_trades),
            "closed_trades": len(self.closed_trades),
            "total_profit": total_profit,
            "daily_profit": self.daily_profit,
            "daily_loss": self.daily_loss,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": winning_trades / (winning_trades + losing_trades) if (winning_trades + losing_trades) > 0 else 0
        }
    
    def close_all_trades(self, exit_price: float) -> List[Trade]:
        """Close all open trades at a specific price"""
        closed = []
        for trade in self.open_trades[:]:
            trade.exit_price = exit_price
            trade.exit_time = datetime.utcnow()
            trade.exit_reason = "Manual Close"
            trade.profit, trade.profit_percent = trade.calculate_profit(exit_price)
            trade.status = TradeStatus.CLOSED
            
            self.daily_profit += trade.profit if trade.profit > 0 else 0
            self.daily_loss += trade.profit if trade.profit < 0 else 0
            
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            closed.append(trade)
        
        return closed


# Global instance
scalping_strategy = ScalpingStrategy()


if __name__ == "__main__":
    import asyncio
    
    async def test():
        strategy = ScalpingStrategy()
        
        async with BIQuoteClient() as client:
            # Run a few cycles
            for i in range(5):
                result = await strategy.run_scalping_cycle(client)
                print(f"\nCycle {i+1}:")
                print(f"  Status: {result['status']}")
                print(f"  Price: {result['current_price']}")
                print(f"  Trades Executed: {result['trades_executed']}")
                print(f"  Daily Trades: {result['daily_trades']}/{config.trading.DAILY_TRADES_LIMIT}")
                
                if result.get('signal'):
                    signal = result['signal']
                    print(f"  Signal: {signal['direction']} at {signal['entry_price']}")
                    print(f"    SL: {signal['stop_loss']}, TP: {signal['take_profit']}")
                    print(f"    Reason: {signal['reason']}")
                
                # Small delay
                await asyncio.sleep(1)
            
            # Print summary
            summary = strategy.get_trade_summary()
            print("\nTrading Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
    
    asyncio.run(test())

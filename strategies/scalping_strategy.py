"""
Aggressive Scalping Strategy
Primary driver: Japanese Candlestick Patterns
Secondary: Technical Indicators
Low barriers - bot decides based on combined smart score
"""

import logging
import uuid
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from config.settings import config
from modules.data_fetcher import Candle
from modules.pattern_detector import PatternDetector, pattern_detector, CandlestickPattern
from modules.technical_analyzer import TechnicalAnalyzer, technical_analyzer, AnalysisResult

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class TradeSignal:
    signal_id: str
    timestamp: datetime
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    strength: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    patterns: List[str] = field(default_factory=list)
    timeframe: str = "1m"
    risk_percent: float = 0.02
    lot_size: float = 0.1
    candle_score: float = 0.0
    indicator_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "entry_price": round(self.entry_price, 5),
            "stop_loss": round(self.stop_loss, 5),
            "take_profit": round(self.take_profit, 5),
            "confidence": round(self.confidence, 3),
            "strength": round(self.strength, 3),
            "reason": self.reason,
            "indicators": self.indicators,
            "patterns": self.patterns,
            "timeframe": self.timeframe,
            "risk_percent": self.risk_percent,
            "lot_size": self.lot_size,
            "candle_score": round(self.candle_score, 3),
            "indicator_score": round(self.indicator_score, 3)
        }


@dataclass
class Trade:
    trade_id: str
    signal_id: str
    direction: TradeDirection
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    lot_size: float
    status: TradeStatus = TradeStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    profit: Optional[float] = None
    profit_percent: Optional[float] = None
    reason: str = ""
    patterns: List[str] = field(default_factory=list)
    trailing_activated: bool = False
    highest_price: float = 0.0
    lowest_price: float = 999999.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "signal_id": self.signal_id,
            "direction": self.direction.value,
            "entry_price": round(self.entry_price, 5),
            "entry_time": self.entry_time.isoformat(),
            "stop_loss": round(self.stop_loss, 5),
            "take_profit": round(self.take_profit, 5),
            "lot_size": self.lot_size,
            "status": self.status.value,
            "exit_price": round(self.exit_price, 5) if self.exit_price else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "profit": round(self.profit, 2) if self.profit is not None else None,
            "profit_percent": round(self.profit_percent, 3) if self.profit_percent is not None else None,
            "reason": self.reason,
            "patterns": self.patterns,
            "trailing_activated": self.trailing_activated
        }


class ScalpingStrategy:
    def __init__(self):
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.daily_trades = 0
        self.current_day = date.today()
        self.detector = pattern_detector
        self.analyzer = technical_analyzer
        self.cfg = config.trading
        self.sig_cfg = config.signal

    def _check_new_day(self):
        today = date.today()
        if today != self.current_day:
            self.daily_trades = 0
            self.current_day = today
            logger.info("New trading day - counters reset")

    def _calc_sl_tp(self, direction: TradeDirection, entry: float, atr: float) -> tuple:
        sl_dist = max(self.cfg.DEFAULT_STOP_LOSS * 0.1, atr * 1.1)
        tp_dist = max(self.cfg.DEFAULT_TAKE_PROFIT * 0.1, atr * 2.2)
        if direction == TradeDirection.BUY:
            return entry - sl_dist, entry + tp_dist
        return entry + sl_dist, entry - tp_dist

    def generate_signal(
        self,
        candles_1m: List[Candle],
        analysis_1m: AnalysisResult,
        current_price: float,
        multi_tf_patterns: Dict[str, List] = None
    ) -> Optional[TradeSignal]:
        self._check_new_day()
        if self.daily_trades >= self.cfg.DAILY_TRADES_LIMIT:
            logger.debug("Daily trade limit reached")
            return None
        if len(self.open_trades) >= config.risk.MAX_OPEN_TRADES:
            return None
        if len(candles_1m) < 30:
            return None

        candle_score_data = self.detector.get_directional_score(candles_1m)
        candle_buy = candle_score_data["buy_score"]
        candle_sell = candle_score_data["sell_score"]
        best_patterns = candle_score_data.get("patterns", [])

        ind_score_data = self.analyzer.get_indicator_score(analysis_1m)
        ind_buy = ind_score_data["buy_score"]
        ind_sell = ind_score_data["sell_score"]

        w_c = self.sig_cfg.CANDLE_PATTERN_WEIGHT
        w_i = self.sig_cfg.INDICATOR_WEIGHT
        final_buy = candle_buy * w_c + ind_buy * w_i
        final_sell = candle_sell * w_c + ind_sell * w_i

        if analysis_1m.volume_ratio > 1.6:
            if final_buy > final_sell:
                final_buy *= 1.15
            else:
                final_sell *= 1.15

        if final_buy > final_sell and final_buy >= self.cfg.MIN_SIGNAL_STRENGTH:
            direction = TradeDirection.BUY
            strength = min(0.98, final_buy)
            confidence = min(0.95, (candle_buy + ind_buy) / 2 + 0.15)
        elif final_sell > final_buy and final_sell >= self.cfg.MIN_SIGNAL_STRENGTH:
            direction = TradeDirection.SELL
            strength = min(0.98, final_sell)
            confidence = min(0.95, (candle_sell + ind_sell) / 2 + 0.15)
        else:
            return None

        if confidence < self.cfg.MIN_CONFIDENCE:
            return None

        pattern_names = [p.get("name_ar") or p.get("name") for p in best_patterns[:3]]
        reason_parts = []
        if pattern_names:
            reason_parts.append(f"\u0634\u0645\u0648\u0639 \u064a\u0627\u0628\u0627\u0646\u064a\u0629: {', '.join(pattern_names)}")
        if analysis_1m.trend != "NEUTRAL":
            reason_parts.append(f"\u0627\u062a\u062c\u0627\u0647 {analysis_1m.trend}")
        if analysis_1m.rsi < 35:
            reason_parts.append(f"RSI \u0645\u0634\u062a\u0631\u0649 ({analysis_1m.rsi:.1f})")
        elif analysis_1m.rsi > 65:
            reason_parts.append(f"RSI \u0645\u0628\u064a\u0639 ({analysis_1m.rsi:.1f})")
        if analysis_1m.volume_ratio > 1.5:
            reason_parts.append(f"\u062d\u062c\u0645 \u0645\u0631\u062a\u0641\u0639 \u00d7{analysis_1m.volume_ratio:.1f}")
        reason = " | ".join(reason_parts) if reason_parts else "\u062a\u062d\u0644\u064a\u0644 \u0630\u0643\u064a \u0645\u062a\u0639\u062f\u062f \u0627\u0644\u0639\u0648\u0627\u0645\u0644"

        sl, tp = self._calc_sl_tp(direction, current_price, analysis_1m.atr or 1.5)

        signal = TradeSignal(
            signal_id=str(uuid.uuid4())[:12],
            timestamp=datetime.utcnow(),
            direction=direction,
            entry_price=current_price,
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            confidence=confidence,
            strength=strength,
            reason=reason,
            indicators={
                "rsi": analysis_1m.rsi,
                "macd_hist": analysis_1m.macd_hist,
                "atr": analysis_1m.atr,
                "trend": analysis_1m.trend,
                "volume_ratio": analysis_1m.volume_ratio,
                "stoch_k": analysis_1m.stoch_k
            },
            patterns=[p.get("name", "") for p in best_patterns[:4]],
            timeframe="1m",
            risk_percent=config.risk.MAX_TRADE_RISK_PERCENT,
            lot_size=self.cfg.LOT_SIZE,
            candle_score=candle_buy if direction == TradeDirection.BUY else candle_sell,
            indicator_score=ind_buy if direction == TradeDirection.BUY else ind_sell
        )
        logger.info(f"Signal generated: {direction.value} strength={strength:.2f} conf={confidence:.2f} | {reason}")
        return signal

    def execute_signal(self, signal: TradeSignal) -> Optional[Trade]:
        trade = Trade(
            trade_id=str(uuid.uuid4())[:10],
            signal_id=signal.signal_id,
            direction=signal.direction,
            entry_price=signal.entry_price,
            entry_time=datetime.utcnow(),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            lot_size=signal.lot_size,
            reason=signal.reason,
            patterns=signal.patterns,
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price
        )
        self.open_trades.append(trade)
        self.daily_trades += 1
        logger.info(f"Trade opened: {trade.trade_id} {trade.direction.value} @ {trade.entry_price}")
        return trade

    def check_exit(self, trade: Trade, current_price: float) -> bool:
        if trade.status != TradeStatus.OPEN:
            return False

        if current_price > trade.highest_price:
            trade.highest_price = current_price
        if current_price < trade.lowest_price:
            trade.lowest_price = current_price

        if self.cfg.TRAILING_STOP:
            dist = self.cfg.TRAILING_STOP_DISTANCE * 0.1
            if trade.direction == TradeDirection.BUY:
                if current_price - trade.entry_price > dist * 1.5:
                    new_sl = current_price - dist
                    if new_sl > trade.stop_loss:
                        trade.stop_loss = new_sl
                        trade.trailing_activated = True
            else:
                if trade.entry_price - current_price > dist * 1.5:
                    new_sl = current_price + dist
                    if new_sl < trade.stop_loss:
                        trade.stop_loss = new_sl
                        trade.trailing_activated = True

        hit_sl = False
        hit_tp = False
        if trade.direction == TradeDirection.BUY:
            hit_sl = current_price <= trade.stop_loss
            hit_tp = current_price >= trade.take_profit
        else:
            hit_sl = current_price >= trade.stop_loss
            hit_tp = current_price <= trade.take_profit

        if hit_sl or hit_tp:
            trade.exit_price = current_price
            trade.exit_time = datetime.utcnow()
            trade.status = TradeStatus.CLOSED
            if trade.direction == TradeDirection.BUY:
                trade.profit = (current_price - trade.entry_price) * trade.lot_size * 100
            else:
                trade.profit = (trade.entry_price - current_price) * trade.lot_size * 100
            trade.profit_percent = (trade.profit / (trade.entry_price * trade.lot_size)) * 100 if trade.entry_price else 0
            trade.exit_reason = "Take Profit" if hit_tp else "Stop Loss"
            if trade.trailing_activated and hit_sl:
                trade.exit_reason = "Trailing Stop"
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            logger.info(f"Trade closed: {trade.trade_id} {trade.exit_reason} P/L={trade.profit:.2f}")
            return True
        return False

    def get_open_trades_dict(self) -> List[Dict]:
        return [t.to_dict() for t in self.open_trades]

    def get_closed_trades_dict(self, limit: int = 50) -> List[Dict]:
        return [t.to_dict() for t in self.closed_trades[-limit:]]


scalping_strategy = ScalpingStrategy()

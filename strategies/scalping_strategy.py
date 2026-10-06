"""
Aggressive Scalping Strategy
- 1 open trade only
- TP1 / TP2 / TP3 with partial management
- Max 50 min if losing, unlimited if winning
- Analyze last 20 candles for entry
- OHLC high/low for TP/SL (no missed targets)
- Persist trades to disk (survive Render restart)
"""

import logging
import json
import os
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from config.settings import config
from modules.data_fetcher import Candle
from modules.pattern_detector import pattern_detector
from modules.technical_analyzer import technical_analyzer, AnalysisResult

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
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    confidence: float = 0.0
    strength: float = 0.0
    score: int = 0
    reason: str = ""
    pattern_name: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    patterns: List[str] = field(default_factory=list)
    timeframe: str = "1m"
    risk_percent: float = 0.02
    lot_size: float = 0.1
    candle_score: float = 0.0
    indicator_score: float = 0.0
    multi_tf: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "entry_price": round(self.entry_price, 3),
            "stop_loss": round(self.stop_loss, 3),
            "take_profit": round(self.take_profit, 3),
            "tp1": round(self.tp1, 3),
            "tp2": round(self.tp2, 3),
            "tp3": round(self.tp3, 3),
            "confidence": round(self.confidence, 3),
            "strength": round(self.strength, 3),
            "score": self.score,
            "reason": self.reason,
            "pattern_name": self.pattern_name,
            "indicators": self.indicators,
            "patterns": self.patterns,
            "multi_tf": self.multi_tf,
            "timeframe": self.timeframe,
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
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    lot_size: float = 0.1
    status: TradeStatus = TradeStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    profit: Optional[float] = None
    profit_percent: Optional[float] = None
    reason: str = ""
    patterns: List[str] = field(default_factory=list)
    pattern_name: str = ""
    score: int = 0
    trailing_activated: bool = False
    tp1_hit: bool = False
    tp2_hit: bool = False
    be_moved: bool = False
    highest_price: float = 0.0
    lowest_price: float = 999999.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "signal_id": self.signal_id,
            "direction": self.direction.value,
            "entry_price": round(self.entry_price, 3),
            "entry_time": self.entry_time.isoformat(),
            "stop_loss": round(self.stop_loss, 3),
            "take_profit": round(self.take_profit, 3),
            "tp1": round(self.tp1, 3),
            "tp2": round(self.tp2, 3),
            "tp3": round(self.tp3, 3),
            "lot_size": self.lot_size,
            "status": self.status.value,
            "exit_price": round(self.exit_price, 3) if self.exit_price else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "profit": round(self.profit, 2) if self.profit is not None else None,
            "profit_percent": round(self.profit_percent, 3) if self.profit_percent is not None else None,
            "reason": self.reason,
            "patterns": self.patterns,
            "pattern_name": self.pattern_name,
            "score": self.score,
            "tp1_hit": self.tp1_hit,
            "tp2_hit": self.tp2_hit,
            "be_moved": self.be_moved,
            "trailing_activated": self.trailing_activated,
            "highest_price": self.highest_price,
            "lowest_price": self.lowest_price,
        }


class ScalpingStrategy:
    MAX_LOSS_DURATION_MIN = 50
    TRADES_FILE = "data/open_trades.json"

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

    def _calc_sl_tp(self, direction: TradeDirection, entry: float, atr: float) -> Tuple[float, float, float, float]:
        atr = max(atr or 1.5, 0.8)
        sl_dist = max(3.0, atr * 1.15)
        tp1_dist = max(2.0, atr * 0.9)
        tp2_dist = max(4.0, atr * 1.8)
        tp3_dist = max(6.0, atr * 2.8)
        if direction == TradeDirection.BUY:
            return round(entry - sl_dist, 3), round(entry + tp1_dist, 3), round(entry + tp2_dist, 3), round(entry + tp3_dist, 3)
        return round(entry + sl_dist, 3), round(entry - tp1_dist, 3), round(entry - tp2_dist, 3), round(entry - tp3_dist, 3)

    def generate_signal(self, candles_1m: List[Candle], analysis_1m: AnalysisResult, current_price: float, multi_tf_patterns: Dict[str, List] = None) -> Optional[TradeSignal]:
        self._check_new_day()
        if self.daily_trades >= self.cfg.DAILY_TRADES_LIMIT:
            return None
        if len(self.open_trades) >= 1:
            return None
        if len(candles_1m) < 20:
            return None

        recent = candles_1m[-20:]
        candle_score_data = self.detector.get_directional_score(recent)
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
                final_buy *= 1.12
            else:
                final_sell *= 1.12

        if final_buy > final_sell and final_buy >= self.cfg.MIN_SIGNAL_STRENGTH:
            direction = TradeDirection.BUY
            strength = min(0.98, final_buy)
            confidence = min(0.95, (candle_buy + ind_buy) / 2 + 0.12)
        elif final_sell > final_buy and final_sell >= self.cfg.MIN_SIGNAL_STRENGTH:
            direction = TradeDirection.SELL
            strength = min(0.98, final_sell)
            confidence = min(0.95, (candle_sell + ind_sell) / 2 + 0.12)
        else:
            return None

        if confidence < self.cfg.MIN_CONFIDENCE:
            return None

        score = int(min(99, max(50, strength * 100)))
        pattern_name = ""
        if best_patterns:
            pattern_name = best_patterns[0].get("name") or best_patterns[0].get("name_ar") or ""

        # Reject strong conflict (e.g. Gravestone Doji for BUY)
        bearish_names = ("gravestone", "shooting star", "evening star", "bearish engul", "hanging man", "dark cloud")
        bullish_names = ("hammer", "morning star", "bullish engul", "dragonfly", "inverted hammer", "piercing")
        pname = (pattern_name or "").lower()
        if direction == TradeDirection.BUY and any(x in pname for x in bearish_names):
            logger.info(f"Skip BUY - conflicting pattern {pattern_name}")
            return None
        if direction == TradeDirection.SELL and any(x in pname for x in bullish_names):
            logger.info(f"Skip SELL - conflicting pattern {pattern_name}")
            return None

        trend = analysis_1m.trend or "NEUTRAL"
        multi_tf = f"M1: {trend}"

        pattern_names = [p.get("name_ar") or p.get("name") for p in best_patterns[:3]]
        reason_parts = []
        if pattern_names:
            reason_parts.append(f"\u0634\u0645\u0648\u0639: {', '.join(pattern_names)}")
        if analysis_1m.rsi < 35:
            reason_parts.append(f"RSI \u0645\u0634\u062a\u0631\u0649 ({analysis_1m.rsi:.1f})")
        elif analysis_1m.rsi > 65:
            reason_parts.append(f"RSI \u0645\u0628\u064a\u0639 ({analysis_1m.rsi:.1f})")
        reason = " | ".join(reason_parts) if reason_parts else "\u062a\u062d\u0644\u064a\u0644 \u0630\u0643\u064a 20 \u0634\u0645\u0639\u0629"

        sl, tp1, tp2, tp3 = self._calc_sl_tp(direction, current_price, analysis_1m.atr or 1.5)

        ts = datetime.utcnow().strftime("%Y%m%d")
        short = str(uuid.uuid4())[:8].upper()
        signal_id = f"{direction.value}-{ts}-{short}"

        signal = TradeSignal(
            signal_id=signal_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            entry_price=round(current_price, 3),
            stop_loss=sl,
            take_profit=tp3,
            tp1=tp1, tp2=tp2, tp3=tp3,
            confidence=confidence,
            strength=strength,
            score=score,
            reason=reason,
            pattern_name=pattern_name,
            indicators={
                "rsi": round(analysis_1m.rsi, 1),
                "macd_hist": round(analysis_1m.macd_hist, 4),
                "atr": round(analysis_1m.atr or 0, 3),
                "trend": analysis_1m.trend,
                "volume_ratio": round(analysis_1m.volume_ratio, 2),
            },
            patterns=[p.get("name", "") for p in best_patterns[:4]],
            multi_tf=multi_tf,
            timeframe="1m",
            risk_percent=config.risk.MAX_TRADE_RISK_PERCENT,
            lot_size=self.cfg.LOT_SIZE,
            candle_score=candle_buy if direction == TradeDirection.BUY else candle_sell,
            indicator_score=ind_buy if direction == TradeDirection.BUY else ind_sell,
        )
        logger.info(f"Signal: {direction.value} score={score} entry={current_price:.2f} | {pattern_name}")
        return signal

    def execute_signal(self, signal: TradeSignal) -> Optional[Trade]:
        if len(self.open_trades) >= 1:
            return None
        trade = Trade(
            trade_id=signal.signal_id,
            signal_id=signal.signal_id,
            direction=signal.direction,
            entry_price=signal.entry_price,
            entry_time=datetime.utcnow(),
            stop_loss=signal.stop_loss,
            take_profit=signal.tp3,
            tp1=signal.tp1, tp2=signal.tp2, tp3=signal.tp3,
            lot_size=signal.lot_size,
            reason=signal.reason,
            patterns=signal.patterns,
            pattern_name=signal.pattern_name,
            score=signal.score,
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price,
        )
        self.open_trades.append(trade)
        self.daily_trades += 1
        self._save_trades()
        logger.info(f"Trade opened: {trade.trade_id} {trade.direction.value} @ {trade.entry_price}")
        return trade

    def check_exit(
        self,
        trade: Trade,
        current_price: float,
        bar_high: float = None,
        bar_low: float = None,
    ) -> Tuple[bool, list]:
        """Returns (closed, events_list). Uses bar high/low so TP/SL not missed on wicks."""
        if trade.status != TradeStatus.OPEN:
            return False, []

        hi = bar_high if bar_high is not None else current_price
        lo = bar_low if bar_low is not None else current_price

        if hi > trade.highest_price:
            trade.highest_price = hi
        if lo < trade.lowest_price:
            trade.lowest_price = lo

        events = []
        is_buy = trade.direction == TradeDirection.BUY

        age_min = (datetime.utcnow() - trade.entry_time).total_seconds() / 60
        floating = (current_price - trade.entry_price) if is_buy else (trade.entry_price - current_price)
        if age_min >= self.MAX_LOSS_DURATION_MIN and floating < 0:
            trade.exit_price = current_price
            trade.exit_time = datetime.utcnow()
            trade.status = TradeStatus.CLOSED
            trade.exit_reason = "Time Limit (50m loss)"
            trade.profit = floating * trade.lot_size * 100
            trade.profit_percent = (floating / trade.entry_price) * 100 if trade.entry_price else 0
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            self._save_trades()
            return True, ["TIME"]

        if not trade.tp1_hit:
            hit_tp1 = (hi >= trade.tp1) if is_buy else (lo <= trade.tp1)
            if hit_tp1:
                trade.tp1_hit = True
                be = trade.entry_price + (0.15 if is_buy else -0.15)
                trade.stop_loss = round(be, 3)
                trade.be_moved = True
                events.append("TP1")
                logger.info(f"TP1 hit {trade.trade_id} -> SL to BE {trade.stop_loss}")

        if trade.tp1_hit and not trade.tp2_hit:
            hit_tp2 = (hi >= trade.tp2) if is_buy else (lo <= trade.tp2)
            if hit_tp2:
                trade.tp2_hit = True
                new_sl = trade.tp1 + (0.2 if is_buy else -0.2)
                if is_buy and new_sl > trade.stop_loss:
                    trade.stop_loss = round(new_sl, 3)
                elif not is_buy and new_sl < trade.stop_loss:
                    trade.stop_loss = round(new_sl, 3)
                trade.trailing_activated = True
                events.append("TP2")
                logger.info(f"TP2 hit {trade.trade_id}")

        hit_tp3 = (hi >= trade.tp3) if is_buy else (lo <= trade.tp3)
        hit_sl = (lo <= trade.stop_loss) if is_buy else (hi >= trade.stop_loss)

        if hit_tp3 or hit_sl:
            if hit_tp3:
                trade.exit_price = trade.tp3
                trade.exit_reason = "TP3 Full Target"
                events.append("TP3")
            elif trade.be_moved and hit_sl:
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "Break Even"
                events.append("BE")
            else:
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "Stop Loss"
                events.append("SL")

            trade.exit_time = datetime.utcnow()
            trade.status = TradeStatus.CLOSED
            px = trade.exit_price
            if is_buy:
                trade.profit = (px - trade.entry_price) * trade.lot_size * 100
            else:
                trade.profit = (trade.entry_price - px) * trade.lot_size * 100
            trade.profit_percent = (trade.profit / (trade.entry_price * trade.lot_size)) * 100 if trade.entry_price else 0
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            self._save_trades()
            logger.info(f"Trade closed: {trade.trade_id} {trade.exit_reason} P/L={trade.profit:.2f}")
            return True, events

        if events:
            self._save_trades()
        return False, events

    def _save_trades(self):
        try:
            os.makedirs("data", exist_ok=True)
            payload = {
                "open": [t.to_dict() for t in self.open_trades],
                "closed": [t.to_dict() for t in self.closed_trades[-100:]],
                "daily_trades": self.daily_trades,
                "current_day": self.current_day.isoformat(),
            }
            with open(self.TRADES_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"save trades failed: {e}")

    def load_trades(self):
        try:
            if not os.path.exists(self.TRADES_FILE):
                return
            with open(self.TRADES_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.daily_trades = payload.get("daily_trades", 0)
            day = payload.get("current_day")
            if day:
                self.current_day = date.fromisoformat(day)
            self.open_trades = []
            for d in payload.get("open", []):
                t = self._trade_from_dict(d)
                if t:
                    self.open_trades.append(t)
            self.closed_trades = []
            for d in payload.get("closed", []):
                t = self._trade_from_dict(d)
                if t:
                    self.closed_trades.append(t)
            logger.info(f"Loaded {len(self.open_trades)} open + {len(self.closed_trades)} closed trades")
        except Exception as e:
            logger.warning(f"load trades failed: {e}")

    def _trade_from_dict(self, d: Dict) -> Optional[Trade]:
        try:
            direction = TradeDirection.BUY if d.get("direction") == "BUY" else TradeDirection.SELL
            status = TradeStatus.OPEN if d.get("status") == "OPEN" else TradeStatus.CLOSED
            entry_time = datetime.fromisoformat(d["entry_time"]) if d.get("entry_time") else datetime.utcnow()
            exit_time = datetime.fromisoformat(d["exit_time"]) if d.get("exit_time") else None
            return Trade(
                trade_id=d.get("trade_id", ""),
                signal_id=d.get("signal_id", ""),
                direction=direction,
                entry_price=float(d.get("entry_price", 0)),
                entry_time=entry_time,
                stop_loss=float(d.get("stop_loss", 0)),
                take_profit=float(d.get("take_profit", 0)),
                tp1=float(d.get("tp1", 0)),
                tp2=float(d.get("tp2", 0)),
                tp3=float(d.get("tp3", 0)),
                lot_size=float(d.get("lot_size", 0.1)),
                status=status,
                exit_price=float(d["exit_price"]) if d.get("exit_price") is not None else None,
                exit_time=exit_time,
                exit_reason=d.get("exit_reason"),
                profit=d.get("profit"),
                profit_percent=d.get("profit_percent"),
                reason=d.get("reason", ""),
                patterns=d.get("patterns") or [],
                pattern_name=d.get("pattern_name", ""),
                score=int(d.get("score", 0)),
                trailing_activated=bool(d.get("trailing_activated", False)),
                tp1_hit=bool(d.get("tp1_hit", False)),
                tp2_hit=bool(d.get("tp2_hit", False)),
                be_moved=bool(d.get("be_moved", False)),
                highest_price=float(d.get("highest_price") or d.get("entry_price") or 0),
                lowest_price=float(d.get("lowest_price") or d.get("entry_price") or 999999),
            )
        except Exception as e:
            logger.warning(f"trade_from_dict error: {e}")
            return None

    def get_open_trades_dict(self) -> List[Dict]:
        return [t.to_dict() for t in self.open_trades]

    def get_closed_trades_dict(self, limit: int = 50) -> List[Dict]:
        return [t.to_dict() for t in self.closed_trades[-limit:]]


scalping_strategy = ScalpingStrategy()

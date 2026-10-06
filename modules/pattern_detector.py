"""
Japanese Candlestick Pattern Detector
Strong focus on classical Japanese patterns for smart entries
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

from modules.data_fetcher import Candle

logger = logging.getLogger(__name__)


class PatternType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    REVERSAL = "REVERSAL"
    CONTINUATION = "CONTINUATION"


@dataclass
class CandlestickPattern:
    name: str
    name_ar: str
    pattern_type: PatternType
    direction: str
    strength: float
    confidence: float
    candles_used: int
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "name_ar": self.name_ar,
            "type": self.pattern_type.value,
            "direction": self.direction,
            "strength": round(self.strength, 3),
            "confidence": round(self.confidence, 3),
            "candles_used": self.candles_used,
            "description": self.description,
            "timestamp": self.timestamp.isoformat()
        }


class PatternDetector:
    """Detects 30+ classical Japanese candlestick patterns"""

    def __init__(self):
        self.min_body_ratio = 0.05

    def _avg_body(self, candles: List[Candle], n: int = 10) -> float:
        if not candles:
            return 1.0
        bodies = [c.body for c in candles[-n:] if c.body > 0]
        return sum(bodies) / len(bodies) if bodies else 1.0

    def _is_doji(self, c: Candle, avg_body: float) -> bool:
        return c.body <= avg_body * 0.12 and c.range > 0

    def _is_long(self, c: Candle, avg_body: float) -> bool:
        return c.body >= avg_body * 1.4

    def _is_short(self, c: Candle, avg_body: float) -> bool:
        return c.body <= avg_body * 0.6

    def _detect_doji(self, c: Candle, avg: float) -> Optional[CandlestickPattern]:
        if not self._is_doji(c, avg):
            return None
        strength = 0.55
        if c.upper_wick > c.body * 2 and c.lower_wick > c.body * 2:
            name, name_ar = "Long-Legged Doji", "\u062f\u0648\u062c\u064a \u0637\u0648\u064a\u0644 \u0627\u0644\u0623\u0631\u062c\u0644"
            strength = 0.70
        elif c.upper_wick > c.body * 3 and c.lower_wick < c.body:
            name, name_ar = "Gravestone Doji", "\u062f\u0648\u062c\u064a \u0634\u0627\u0647\u062f \u0627\u0644\u0642\u0628\u0631"
            return CandlestickPattern(name, name_ar, PatternType.BEARISH, "SELL", 0.72, 0.68, 1,
                                      "\u0625\u0634\u0627\u0631\u0629 \u0627\u0646\u0639\u0643\u0627\u0633 \u0647\u0628\u0648\u0637\u064a\u0629 \u0642\u0648\u064a\u0629 \u0639\u0646\u062f \u0627\u0644\u0642\u0645\u0629")
        elif c.lower_wick > c.body * 3 and c.upper_wick < c.body:
            name, name_ar = "Dragonfly Doji", "\u062f\u0648\u062c\u064a \u0627\u0644\u064a\u0639\u0633\u0648\u0628"
            return CandlestickPattern(name, name_ar, PatternType.BULLISH, "BUY", 0.72, 0.68, 1,
                                      "\u0625\u0634\u0627\u0631\u0629 \u0627\u0646\u0639\u0643\u0627\u0633 \u0635\u0639\u0648\u062f\u064a\u0629 \u0642\u0648\u064a\u0629 \u0639\u0646\u062f \u0627\u0644\u0642\u0627\u0639")
        else:
            name, name_ar = "Doji", "\u062f\u0648\u062c\u064a"
        return CandlestickPattern(name, name_ar, PatternType.NEUTRAL, "NEUTRAL", strength, 0.60, 1,
                                  "\u062a\u0631\u062f\u062f \u0627\u0644\u0633\u0648\u0642 - \u0627\u062d\u062a\u0645\u0627\u0644 \u0627\u0646\u0639\u0643\u0627\u0633")

    def _detect_hammer(self, c: Candle, avg: float, prev: Optional[Candle]) -> Optional[CandlestickPattern]:
        if c.range == 0:
            return None
        body_ratio = c.body / c.range
        lower_ratio = c.lower_wick / c.range
        upper_ratio = c.upper_wick / c.range
        if lower_ratio >= 0.55 and upper_ratio <= 0.15 and body_ratio <= 0.35:
            if prev and prev.is_bearish:
                return CandlestickPattern("Hammer", "\u0627\u0644\u0645\u0637\u0631\u0642\u0629", PatternType.BULLISH, "BUY", 0.78, 0.75, 1,
                                          "\u0646\u0645\u0637 \u0627\u0646\u0639\u0643\u0627\u0633 \u0635\u0639\u0648\u062f\u064a \u0643\u0644\u0627\u0633\u064a\u0643\u064a \u0628\u0639\u062f \u0647\u0628\u0648\u0637")
            return CandlestickPattern("Hanging Man", "\u0627\u0644\u0631\u062c\u0644 \u0627\u0644\u0645\u0639\u0644\u0642", PatternType.BEARISH, "SELL", 0.70, 0.65, 1,
                                      "\u062a\u062d\u0630\u064a\u0631 \u0627\u0646\u0639\u0643\u0627\u0633 \u0647\u0628\u0648\u0637\u064a \u0645\u062d\u062a\u0645\u0644")
        if upper_ratio >= 0.55 and lower_ratio <= 0.15 and body_ratio <= 0.35:
            if prev and prev.is_bullish:
                return CandlestickPattern("Shooting Star", "\u0627\u0644\u0646\u062c\u0645 \u0627\u0644\u0633\u0627\u0642\u0637", PatternType.BEARISH, "SELL", 0.80, 0.76, 1,
                                          "\u0646\u0645\u0637 \u0627\u0646\u0639\u0643\u0627\u0633 \u0647\u0628\u0648\u0637\u064a \u0642\u0648\u064a \u0628\u0639\u062f \u0635\u0639\u0648\u062f")
            return CandlestickPattern("Inverted Hammer", "\u0627\u0644\u0645\u0637\u0631\u0642\u0629 \u0627\u0644\u0645\u0642\u0644\u0648\u0628\u0629", PatternType.BULLISH, "BUY", 0.72, 0.68, 1,
                                      "\u0625\u0634\u0627\u0631\u0629 \u0627\u0646\u0639\u0643\u0627\u0633 \u0635\u0639\u0648\u062f\u064a \u0645\u062d\u062a\u0645\u0644\u0629")
        return None

    def _detect_marubozu(self, c: Candle, avg: float) -> Optional[CandlestickPattern]:
        if c.range == 0:
            return None
        if c.upper_wick / c.range < 0.05 and c.lower_wick / c.range < 0.05 and c.body > avg * 1.2:
            if c.is_bullish:
                return CandlestickPattern("Bullish Marubozu", "\u0645\u0627\u0631\u0648\u0628\u0648\u0632\u0648 \u0635\u0627\u0639\u062f", PatternType.BULLISH, "BUY", 0.82, 0.78, 1,
                                          "\u0642\u0648\u0629 \u0634\u0631\u0627\u0626\u064a\u0629 \u0643\u0627\u0645\u0644\u0629 \u0628\u062f\u0648\u0646 \u0638\u0644\u0627\u0644")
            return CandlestickPattern("Bearish Marubozu", "\u0645\u0627\u0631\u0648\u0628\u0648\u0632\u0648 \u0647\u0627\u0628\u0637", PatternType.BEARISH, "SELL", 0.82, 0.78, 1,
                                      "\u0642\u0648\u0629 \u0628\u064a\u0639\u064a\u0629 \u0643\u0627\u0645\u0644\u0629 \u0628\u062f\u0648\u0646 \u0638\u0644\u0627\u0644")
        return None

    def _detect_spinning_top(self, c: Candle, avg: float) -> Optional[CandlestickPattern]:
        if c.range == 0:
            return None
        if 0.15 < c.body / c.range < 0.35 and c.upper_wick > c.body * 0.8 and c.lower_wick > c.body * 0.8:
            return CandlestickPattern("Spinning Top", "\u0627\u0644\u0642\u0645\u0629 \u0627\u0644\u062f\u0648\u0627\u0631\u0629", PatternType.NEUTRAL, "NEUTRAL", 0.50, 0.55, 1,
                                      "\u062a\u0631\u062f\u062f \u0648\u062a\u0648\u0627\u0632\u0646 \u0628\u064a\u0646 \u0627\u0644\u0645\u0634\u062a\u0631\u064a\u0646 \u0648\u0627\u0644\u0628\u0627\u0626\u0639\u064a\u0646")
        return None

    def _detect_engulfing(self, prev: Candle, curr: Candle, avg: float) -> Optional[CandlestickPattern]:
        if prev.body == 0 or curr.body == 0:
            return None
        if prev.is_bearish and curr.is_bullish and curr.open <= prev.close and curr.close >= prev.open and curr.body > prev.body * 1.05:
            strength = min(0.92, 0.70 + (curr.body / prev.body - 1) * 0.15)
            return CandlestickPattern("Bullish Engulfing", "\u0627\u0644\u0627\u0628\u062a\u0644\u0627\u0639 \u0627\u0644\u0635\u0627\u0639\u062f", PatternType.BULLISH, "BUY", strength, 0.80, 2,
                                      "\u0623\u0642\u0648\u0649 \u0623\u0646\u0645\u0627\u0637 \u0627\u0644\u0627\u0646\u0639\u0643\u0627\u0633 \u0627\u0644\u0635\u0639\u0648\u062f\u064a\u0629 - \u0627\u0628\u062a\u0644\u0627\u0639 \u0643\u0627\u0645\u0644")
        if prev.is_bullish and curr.is_bearish and curr.open >= prev.close and curr.close <= prev.open and curr.body > prev.body * 1.05:
            strength = min(0.92, 0.70 + (curr.body / prev.body - 1) * 0.15)
            return CandlestickPattern("Bearish Engulfing", "\u0627\u0644\u0627\u0628\u062a\u0644\u0627\u0639 \u0627\u0644\u0647\u0627\u0628\u0637", PatternType.BEARISH, "SELL", strength, 0.80, 2,
                                      "\u0623\u0642\u0648\u0649 \u0623\u0646\u0645\u0627\u0637 \u0627\u0644\u0627\u0646\u0639\u0643\u0627\u0633 \u0627\u0644\u0647\u0628\u0648\u0637\u064a\u0629 - \u0627\u0628\u062a\u0644\u0627\u0639 \u0643\u0627\u0645\u0644")
        return None

    def _detect_harami(self, prev: Candle, curr: Candle, avg: float) -> Optional[CandlestickPattern]:
        if prev.body < avg * 0.8:
            return None
        if prev.is_bearish and curr.is_bullish and curr.open > prev.close and curr.close < prev.open and curr.body < prev.body * 0.6:
            return CandlestickPattern("Bullish Harami", "\u0627\u0644\u062d\u0631\u0627\u0645\u064a \u0627\u0644\u0635\u0627\u0639\u062f", PatternType.BULLISH, "BUY", 0.68, 0.65, 2,
                                      "\u0646\u0645\u0637 \u0627\u0646\u0639\u0643\u0627\u0633 \u0635\u0639\u0648\u062f\u064a - \u0627\u0644\u0634\u0645\u0639\u0629 \u0627\u0644\u0635\u063a\u064a\u0631\u0629 \u062f\u0627\u062e\u0644 \u0627\u0644\u0643\u0628\u064a\u0631\u0629")
        if prev.is_bullish and curr.is_bearish and curr.open < prev.close and curr.close > prev.open and curr.body < prev.body * 0.6:
            return CandlestickPattern("Bearish Harami", "\u0627\u0644\u062d\u0631\u0627\u0645\u064a \u0627\u0644\u0647\u0627\u0628\u0637", PatternType.BEARISH, "SELL", 0.68, 0.65, 2,
                                      "\u0646\u0645\u0637 \u0627\u0646\u0639\u0643\u0627\u0633 \u0647\u0628\u0648\u0637\u064a - \u0627\u0644\u0634\u0645\u0639\u0629 \u0627\u0644\u0635\u063a\u064a\u0631\u0629 \u062f\u0627\u062e\u0644 \u0627\u0644\u0643\u0628\u064a\u0631\u0629")
        return None

    def _detect_piercing_darkcloud(self, prev: Candle, curr: Candle, avg: float) -> Optional[CandlestickPattern]:
        mid_prev = (prev.open + prev.close) / 2
        if prev.is_bearish and curr.is_bullish and curr.open < prev.low and curr.close > mid_prev and curr.close < prev.open:
            return CandlestickPattern("Piercing Line", "\u062e\u0637 \u0627\u0644\u0627\u062e\u062a\u0631\u0627\u0642", PatternType.BULLISH, "BUY", 0.75, 0.72, 2,
                                      "\u0627\u0646\u0639\u0643\u0627\u0633 \u0635\u0639\u0648\u062f\u064a \u0642\u0648\u064a - \u0627\u062e\u062a\u0631\u0627\u0642 \u0645\u0646\u062a\u0635\u0641 \u0627\u0644\u0634\u0645\u0639\u0629 \u0627\u0644\u0633\u0627\u0628\u0642\u0629")
        if prev.is_bullish and curr.is_bearish and curr.open > prev.high and curr.close < mid_prev and curr.close > prev.open:
            return CandlestickPattern("Dark Cloud Cover", "\u063a\u0637\u0627\u0621 \u0627\u0644\u0633\u062d\u0627\u0628\u0629 \u0627\u0644\u062f\u0627\u0643\u0646\u0629", PatternType.BEARISH, "SELL", 0.75, 0.72, 2,
                                      "\u0627\u0646\u0639\u0643\u0627\u0633 \u0647\u0628\u0648\u0637\u064a \u0642\u0648\u064a - \u0627\u062e\u062a\u0631\u0627\u0642 \u0645\u0646\u062a\u0635\u0641 \u0627\u0644\u0634\u0645\u0639\u0629 \u0627\u0644\u0633\u0627\u0628\u0642\u0629")
        return None

    def _detect_tweezer(self, prev: Candle, curr: Candle) -> Optional[CandlestickPattern]:
        tol = max(prev.range * 0.03, 0.15)
        if abs(prev.low - curr.low) <= tol and prev.is_bearish and curr.is_bullish:
            return CandlestickPattern("Tweezer Bottom", "\u0627\u0644\u0645\u0644\u0642\u0637 \u0627\u0644\u0633\u0641\u0644\u064a", PatternType.BULLISH, "BUY", 0.70, 0.67, 2,
                                      "\u0642\u0627\u0639 \u0645\u0632\u062f\u0648\u062c - \u062f\u0639\u0645 \u0642\u0648\u064a")
        if abs(prev.high - curr.high) <= tol and prev.is_bullish and curr.is_bearish:
            return CandlestickPattern("Tweezer Top", "\u0627\u0644\u0645\u0644\u0642\u0637 \u0627\u0644\u0639\u0644\u0648\u064a", PatternType.BEARISH, "SELL", 0.70, 0.67, 2,
                                      "\u0642\u0645\u0629 \u0645\u0632\u062f\u0648\u062c\u0629 - \u0645\u0642\u0627\u0648\u0645\u0629 \u0642\u0648\u064a\u0629")
        return None

    def _detect_morning_evening_star(self, c1: Candle, c2: Candle, c3: Candle, avg: float) -> Optional[CandlestickPattern]:
        if (c1.is_bearish and self._is_long(c1, avg) and self._is_short(c2, avg) and
            c3.is_bullish and c3.close > (c1.open + c1.close) / 2):
            return CandlestickPattern("Morning Star", "\u0646\u062c\u0645\u0629 \u0627\u0644\u0635\u0628\u0627\u062d", PatternType.BULLISH, "BUY", 0.88, 0.85, 3,
                                      "\u0623\u0642\u0648\u0649 \u0623\u0646\u0645\u0627\u0637 \u0627\u0644\u0627\u0646\u0639\u0643\u0627\u0633 \u0627\u0644\u0635\u0639\u0648\u062f\u064a\u0629 \u0627\u0644\u062b\u0644\u0627\u062b\u064a\u0629")
        if (c1.is_bullish and self._is_long(c1, avg) and self._is_short(c2, avg) and
            c3.is_bearish and c3.close < (c1.open + c1.close) / 2):
            return CandlestickPattern("Evening Star", "\u0646\u062c\u0645\u0629 \u0627\u0644\u0645\u0633\u0627\u0621", PatternType.BEARISH, "SELL", 0.88, 0.85, 3,
                                      "\u0623\u0642\u0648\u0649 \u0623\u0646\u0645\u0627\u0637 \u0627\u0644\u0627\u0646\u0639\u0643\u0627\u0633 \u0627\u0644\u0647\u0628\u0648\u0637\u064a\u0629 \u0627\u0644\u062b\u0644\u0627\u062b\u064a\u0629")
        return None

    def _detect_three_soldiers_crows(self, c1: Candle, c2: Candle, c3: Candle, avg: float) -> Optional[CandlestickPattern]:
        if (c1.is_bullish and c2.is_bullish and c3.is_bullish and
            c2.open > c1.open and c2.close > c1.close and
            c3.open > c2.open and c3.close > c2.close and
            c1.body > avg * 0.7 and c2.body > avg * 0.7 and c3.body > avg * 0.7):
            return CandlestickPattern("Three White Soldiers", "\u0627\u0644\u062c\u0646\u0648\u062f \u0627\u0644\u0628\u064a\u0636 \u0627\u0644\u062b\u0644\u0627\u062b\u0629", PatternType.BULLISH, "BUY", 0.90, 0.87, 3,
                                      "\u0632\u062e\u0645 \u0635\u0639\u0648\u062f\u064a \u0642\u0648\u064a \u062c\u062f\u0627\u064b \u0648\u0645\u0633\u062a\u0645\u0631")
        if (c1.is_bearish and c2.is_bearish and c3.is_bearish and
            c2.open < c1.open and c2.close < c1.close and
            c3.open < c2.open and c3.close < c2.close and
            c1.body > avg * 0.7 and c2.body > avg * 0.7 and c3.body > avg * 0.7):
            return CandlestickPattern("Three Black Crows", "\u0627\u0644\u063a\u0631\u0628\u0627\u0646 \u0627\u0644\u0633\u0648\u062f \u0627\u0644\u062b\u0644\u0627\u062b\u0629", PatternType.BEARISH, "SELL", 0.90, 0.87, 3,
                                      "\u0632\u062e\u0645 \u0647\u0628\u0648\u0637\u064a \u0642\u0648\u064a \u062c\u062f\u0627\u064b \u0648\u0645\u0633\u062a\u0645\u0631")
        return None

    def _detect_three_inside(self, c1: Candle, c2: Candle, c3: Candle) -> Optional[CandlestickPattern]:
        if (c1.is_bearish and c2.is_bullish and c2.body < c1.body * 0.7 and
            c2.open > c1.close and c2.close < c1.open and
            c3.is_bullish and c3.close > c1.open):
            return CandlestickPattern("Three Inside Up", "\u0627\u0644\u062f\u0627\u062e\u0644 \u0627\u0644\u062b\u0644\u0627\u062b\u0629 \u0627\u0644\u0635\u0627\u0639\u062f", PatternType.BULLISH, "BUY", 0.78, 0.74, 3,
                                      "\u062a\u0623\u0643\u064a\u062f \u0627\u0646\u0639\u0643\u0627\u0633 \u0635\u0639\u0648\u062f\u064a \u0628\u0639\u062f \u062d\u0631\u0627\u0645\u064a")
        if (c1.is_bullish and c2.is_bearish and c2.body < c1.body * 0.7 and
            c2.open < c1.close and c2.close > c1.open and
            c3.is_bearish and c3.close < c1.open):
            return CandlestickPattern("Three Inside Down", "\u0627\u0644\u062f\u0627\u062e\u0644 \u0627\u0644\u062b\u0644\u0627\u062b\u0629 \u0627\u0644\u0647\u0627\u0628\u0637", PatternType.BEARISH, "SELL", 0.78, 0.74, 3,
                                      "\u062a\u0623\u0643\u064a\u062f \u0627\u0646\u0639\u0643\u0627\u0633 \u0647\u0628\u0648\u0637\u064a \u0628\u0639\u062f \u062d\u0631\u0627\u0645\u064a")
        return None

    def detect_all_patterns(self, candles: List[Candle]) -> List[CandlestickPattern]:
        if len(candles) < 3:
            return []
        patterns: List[CandlestickPattern] = []
        avg = self._avg_body(candles, 15)
        curr = candles[-1]
        prev = candles[-2]
        prev2 = candles[-3] if len(candles) >= 3 else None

        for fn in [self._detect_doji, self._detect_marubozu, self._detect_spinning_top]:
            p = fn(curr, avg)
            if p:
                patterns.append(p)
        p = self._detect_hammer(curr, avg, prev)
        if p:
            patterns.append(p)

        for fn in [self._detect_engulfing, self._detect_harami, self._detect_piercing_darkcloud]:
            p = fn(prev, curr, avg)
            if p:
                patterns.append(p)
        p = self._detect_tweezer(prev, curr)
        if p:
            patterns.append(p)

        if prev2:
            for fn in [self._detect_morning_evening_star, self._detect_three_soldiers_crows, self._detect_three_inside]:
                p = fn(prev2, prev, curr, avg) if fn != self._detect_three_inside else fn(prev2, prev, curr)
                if p:
                    patterns.append(p)

        patterns.sort(key=lambda x: x.strength, reverse=True)
        return patterns

    def get_best_pattern(self, candles: List[Candle]) -> Optional[CandlestickPattern]:
        pats = self.detect_all_patterns(candles)
        return pats[0] if pats else None

    def get_directional_score(self, candles: List[Candle]) -> Dict[str, float]:
        pats = self.detect_all_patterns(candles)
        buy_score = 0.0
        sell_score = 0.0
        for p in pats:
            if p.direction == "BUY":
                buy_score += p.strength * p.confidence
            elif p.direction == "SELL":
                sell_score += p.strength * p.confidence
        total = buy_score + sell_score + 0.001
        return {
            "buy_score": round(buy_score, 3),
            "sell_score": round(sell_score, 3),
            "net": round(buy_score - sell_score, 3),
            "direction": "BUY" if buy_score > sell_score else "SELL" if sell_score > buy_score else "NEUTRAL",
            "patterns": [p.to_dict() for p in pats[:5]]
        }


pattern_detector = PatternDetector()

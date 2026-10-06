"""
Technical Analyzer - Fast multi-indicator engine
Complements Japanese candlestick analysis (not the main driver)
"""

import numpy as np
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from modules.data_fetcher import Candle

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    timeframe: str
    timestamp: datetime
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    atr: float = 0.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    trend: str = "NEUTRAL"
    trend_strength: float = 0.0
    volume_ratio: float = 1.0
    support: float = 0.0
    resistance: float = 0.0
    momentum: float = 0.0
    volatility: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "rsi": round(self.rsi, 2),
            "macd": round(self.macd, 5),
            "macd_signal": round(self.macd_signal, 5),
            "macd_hist": round(self.macd_hist, 5),
            "bb_upper": round(self.bb_upper, 5),
            "bb_middle": round(self.bb_middle, 5),
            "bb_lower": round(self.bb_lower, 5),
            "atr": round(self.atr, 5),
            "stoch_k": round(self.stoch_k, 2),
            "stoch_d": round(self.stoch_d, 2),
            "ema_fast": round(self.ema_fast, 5),
            "ema_slow": round(self.ema_slow, 5),
            "sma_20": round(self.sma_20, 5),
            "sma_50": round(self.sma_50, 5),
            "trend": self.trend,
            "trend_strength": round(self.trend_strength, 3),
            "volume_ratio": round(self.volume_ratio, 2),
            "support": round(self.support, 5),
            "resistance": round(self.resistance, 5),
            "momentum": round(self.momentum, 3),
            "volatility": round(self.volatility, 5)
        }


class TechnicalAnalyzer:
    def __init__(self):
        pass

    def _closes(self, candles: List[Candle]) -> np.ndarray:
        return np.array([c.close for c in candles], dtype=float)

    def _highs(self, candles: List[Candle]) -> np.ndarray:
        return np.array([c.high for c in candles], dtype=float)

    def _lows(self, candles: List[Candle]) -> np.ndarray:
        return np.array([c.low for c in candles], dtype=float)

    def _volumes(self, candles: List[Candle]) -> np.ndarray:
        return np.array([c.volume for c in candles], dtype=float)

    def _sma(self, data: np.ndarray, period: int) -> float:
        if len(data) < period:
            return float(data[-1]) if len(data) else 0.0
        return float(np.mean(data[-period:]))

    def _ema(self, data: np.ndarray, period: int) -> float:
        if len(data) < period:
            return float(data[-1]) if len(data) else 0.0
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        return float(np.convolve(data[-period:], weights, mode="valid")[-1])

    def _rsi(self, closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))

    def _macd(self, closes: np.ndarray) -> tuple:
        if len(closes) < 26:
            return 0.0, 0.0, 0.0
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd_line = ema12 - ema26
        signal = macd_line * 0.8
        hist = macd_line - signal
        return macd_line, signal, hist

    def _bollinger(self, closes: np.ndarray, period: int = 20, std_dev: float = 2.0) -> tuple:
        if len(closes) < period:
            mid = float(closes[-1])
            return mid, mid, mid
        mid = self._sma(closes, period)
        std = float(np.std(closes[-period:]))
        return mid + std_dev * std, mid, mid - std_dev * std

    def _atr(self, candles: List[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 1.0
        trs = []
        for i in range(-period, 0):
            h = candles[i].high
            l = candles[i].low
            pc = candles[i - 1].close
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        return float(np.mean(trs))

    def _stochastic(self, candles: List[Candle], k_period: int = 14, d_period: int = 3) -> tuple:
        if len(candles) < k_period:
            return 50.0, 50.0
        highs = self._highs(candles[-k_period:])
        lows = self._lows(candles[-k_period:])
        close = candles[-1].close
        highest = np.max(highs)
        lowest = np.min(lows)
        if highest == lowest:
            k = 50.0
        else:
            k = 100 * (close - lowest) / (highest - lowest)
        d = k * 0.7 + 30
        return float(k), float(d)

    def _support_resistance(self, candles: List[Candle], lookback: int = 50) -> tuple:
        if len(candles) < 10:
            return 0.0, 0.0
        subset = candles[-lookback:]
        lows = [c.low for c in subset]
        highs = [c.high for c in subset]
        support = float(np.percentile(lows, 15))
        resistance = float(np.percentile(highs, 85))
        return support, resistance

    def _volume_ratio(self, candles: List[Candle], period: int = 20) -> float:
        if len(candles) < period:
            return 1.0
        vols = self._volumes(candles[-period:])
        avg = np.mean(vols[:-1]) if len(vols) > 1 else 1.0
        if avg == 0:
            return 1.0
        return float(vols[-1] / avg)

    def analyze(self, candles: List[Candle], timeframe: str = "1m") -> AnalysisResult:
        if len(candles) < 20:
            return AnalysisResult(timeframe=timeframe, timestamp=datetime.utcnow())

        closes = self._closes(candles)
        result = AnalysisResult(timeframe=timeframe, timestamp=datetime.utcnow())

        result.rsi = self._rsi(closes)
        result.macd, result.macd_signal, result.macd_hist = self._macd(closes)
        result.bb_upper, result.bb_middle, result.bb_lower = self._bollinger(closes)
        result.atr = self._atr(candles)
        result.stoch_k, result.stoch_d = self._stochastic(candles)
        result.ema_fast = self._ema(closes, 9)
        result.ema_slow = self._ema(closes, 21)
        result.sma_20 = self._sma(closes, 20)
        result.sma_50 = self._sma(closes, 50) if len(closes) >= 50 else result.sma_20
        result.volume_ratio = self._volume_ratio(candles)
        result.support, result.resistance = self._support_resistance(candles)
        result.volatility = result.atr / closes[-1] if closes[-1] else 0.0

        if result.ema_fast > result.ema_slow and closes[-1] > result.sma_20:
            result.trend = "BULLISH"
            result.trend_strength = min(1.0, (result.ema_fast - result.ema_slow) / result.atr * 0.5 + 0.4)
        elif result.ema_fast < result.ema_slow and closes[-1] < result.sma_20:
            result.trend = "BEARISH"
            result.trend_strength = min(1.0, (result.ema_slow - result.ema_fast) / result.atr * 0.5 + 0.4)
        else:
            result.trend = "NEUTRAL"
            result.trend_strength = 0.3

        if len(closes) >= 5:
            result.momentum = (closes[-1] - closes[-5]) / closes[-5] * 100

        return result

    def get_indicator_score(self, result: AnalysisResult) -> Dict[str, float]:
        buy = 0.0
        sell = 0.0

        if result.rsi < 32:
            buy += 0.25
        elif result.rsi < 42:
            buy += 0.12
        elif result.rsi > 68:
            sell += 0.25
        elif result.rsi > 58:
            sell += 0.12

        if result.macd_hist > 0 and result.macd > result.macd_signal:
            buy += 0.18
        elif result.macd_hist < 0 and result.macd < result.macd_signal:
            sell += 0.18

        if result.stoch_k < 25 and result.stoch_k > result.stoch_d:
            buy += 0.15
        elif result.stoch_k > 75 and result.stoch_k < result.stoch_d:
            sell += 0.15

        if result.trend == "BULLISH":
            buy += 0.20 * result.trend_strength
        elif result.trend == "BEARISH":
            sell += 0.20 * result.trend_strength

        if result.volume_ratio > 1.5:
            if buy > sell:
                buy += 0.10
            elif sell > buy:
                sell += 0.10

        return {
            "buy_score": round(buy, 3),
            "sell_score": round(sell, 3),
            "net": round(buy - sell, 3),
            "direction": "BUY" if buy > sell else "SELL" if sell > buy else "NEUTRAL"
        }


technical_analyzer = TechnicalAnalyzer()

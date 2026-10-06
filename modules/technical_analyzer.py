"""
Technical Analyzer Module - Comprehensive technical analysis for XAUUSD
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .data_fetcher import Candle
from config.settings import config

logger = logging.getLogger(__name__)


class SignalType(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK_BUY"
    NEUTRAL = "NEUTRAL"
    WEAK_SELL = "WEAK_SELL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class TrendDirection(Enum):
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    NEUTRAL = "NEUTRAL"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"


class CandlePattern(Enum):
    HAMMER = "HAMMER"
    SHOOTING_STAR = "SHOOTING_STAR"
    ENGULFING_BULLISH = "ENGULFING_BULLISH"
    ENGULFING_BEARISH = "ENGULFING_BEARISH"
    DOJI = "DOJI"
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"
    PIN_BAR = "PIN_BAR"
    INSIDE_BAR = "INSIDE_BAR"
    OUTSIDE_BAR = "OUTSIDE_BAR"


@dataclass
class IndicatorValue:
    """Represents a single indicator value"""
    name: str
    value: float
    signal: Optional[float] = None
    histogram: Optional[float] = None
    

@dataclass
class SupportResistance:
    """Support and Resistance level"""
    price: float
    level_type: str  # "support" or "resistance"
    strength: float  # 0-1
    touches: int
    last_touch: datetime
    

@dataclass
class TrendInfo:
    """Trend information"""
    direction: TrendDirection
    strength: float  # 0-1
    duration: int  # in candles
    confidence: float  # 0-1
    

@dataclass
class AnalysisResult:
    """Complete technical analysis result"""
    timestamp: datetime
    timeframe: str
    
    # Price data
    current_price: float
    high: float
    low: float
    
    # Indicators
    indicators: Dict[str, IndicatorValue] = field(default_factory=dict)
    
    # Trend
    short_term_trend: TrendInfo = None
    medium_term_trend: TrendInfo = None
    long_term_trend: TrendInfo = None
    
    # Support and Resistance
    support_levels: List[SupportResistance] = field(default_factory=list)
    resistance_levels: List[SupportResistance] = field(default_factory=list)
    
    # Patterns
    candle_patterns: List[CandlePattern] = field(default_factory=list)
    
    # Signals
    overall_signal: SignalType = SignalType.NEUTRAL
    signal_strength: float = 0.0
    signal_confidence: float = 0.0
    
    # Volume
    volume: float = 0.0
    volume_spike: bool = False
    
    # Breakout detection
    breakout_upper: bool = False
    breakout_lower: bool = False
    breakout_price: Optional[float] = None
    
    # Reversal detection
    potential_reversal_up: bool = False
    potential_reversal_down: bool = False
    reversal_strength: float = 0.0


class TechnicalAnalyzer:
    """Comprehensive Technical Analyzer for XAUUSD"""
    
    def __init__(self):
        self.lookback_periods = {
            "short": 20,
            "medium": 50,
            "long": 200
        }
        
    def _calculate_sma(self, prices: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return []
        return [sum(prices[i:i+period]) / period for i in range(len(prices) - period + 1)]
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return []
        
        ema = []
        sma = sum(prices[:period]) / period
        multiplier = 2 / (period + 1)
        ema.append(sma)
        
        for i in range(period, len(prices)):
            ema_val = (prices[i] - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_val)
        
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return []
        
        rsi = []
        for i in range(period, len(prices)):
            gains = []
            losses = []
            
            for j in range(i - period + 1, i + 1):
                if j > 0:
                    change = prices[j] - prices[j - 1]
                    if change > 0:
                        gains.append(change)
                    else:
                        losses.append(abs(change))
            
            avg_gain = sum(gains) / period if gains else 0
            avg_loss = sum(losses) / period if losses else 0
            
            if avg_loss == 0:
                rsi.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
        
        return rsi
    
    def _calculate_macd(
        self, 
        prices: List[float], 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD, Signal Line, and Histogram"""
        if len(prices) < slow_period:
            return [], [], []
        
        fast_ema = self._calculate_ema(prices, fast_period)
        slow_ema = self._calculate_ema(prices, slow_period)
        
        if len(fast_ema) < 1 or len(slow_ema) < 1:
            return [], [], []
        
        # Pad to same length
        min_len = min(len(fast_ema), len(slow_ema))
        fast_ema = fast_ema[-min_len:]
        slow_ema = slow_ema[-min_len:]
        
        macd_line = [fast_ema[i] - slow_ema[i] for i in range(min_len)]
        signal_line = self._calculate_ema(macd_line, signal_period)
        histogram = [macd_line[i] - signal_line[i] for i in range(len(signal_line))]
        
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(
        self, 
        prices: List[float], 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return [], [], []
        
        sma = self._calculate_sma(prices, period)
        
        upper_band = []
        lower_band = []
        
        for i in range(len(sma)):
            window = prices[i:i+period]
            std = np.std(window) if len(window) > 1 else 0
            upper_band.append(sma[i] + std * std_dev)
            lower_band.append(sma[i] - std * std_dev)
        
        return upper_band, sma, lower_band
    
    def _calculate_stochastic(
        self, 
        highs: List[float], 
        lows: List[float], 
        closes: List[float], 
        k_period: int = 14, 
        d_period: int = 3
    ) -> Tuple[List[float], List[float]]:
        """Calculate Stochastic Oscillator"""
        if len(highs) < k_period or len(lows) < k_period or len(closes) < k_period:
            return [], []
        
        k_values = []
        d_values = []
        
        for i in range(k_period - 1, len(closes)):
            window_high = max(highs[i - k_period + 1:i + 1])
            window_low = min(lows[i - k_period + 1:i + 1])
            
            if window_high == window_low:
                k = 50
            else:
                k = ((closes[i] - window_low) / (window_high - window_low)) * 100
            
            k_values.append(k)
        
        if k_values:
            d_values = self._calculate_sma(k_values, d_period)
        
        return k_values, d_values
    
    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
        """Calculate Average True Range"""
        if len(highs) < period:
            return []
        
        tr_values = []
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)
        
        atr = self._calculate_sma(tr_values, period)
        return atr
    
    def _calculate_volume_indicators(
        self, 
        volumes: List[float], 
        prices: List[float]
    ) -> Dict[str, float]:
        """Calculate volume-based indicators"""
        if len(volumes) < 20:
            return {}
        
        avg_volume = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]
        
        # Volume ratio
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        # On-Balance Volume (OBV)
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        
        return {
            "volume_ratio": volume_ratio,
            "avg_volume_20": avg_volume,
            "obv": obv
        }
    
    def _detect_candle_patterns(self, candles: List[Candle]) -> List[CandlePattern]:
        """Detect candlestick patterns"""
        if len(candles) < 3:
            return []
        
        patterns = []
        
        # Get last 3 candles
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        # Body size and wick calculations
        def body_size(c):
            return abs(c.close - c.open)
        
        def upper_wick(c):
            return c.high - max(c.open, c.close)
        
        def lower_wick(c):
            return min(c.open, c.close) - c.low
        
        # Hammer (bullish reversal)
        if (lower_wick(c3) >= 2 * body_size(c3) and 
            upper_wick(c3) <= 0.5 * body_size(c3) and
            c3.close > c3.open):
            patterns.append(CandlePattern.HAMMER)
        
        # Shooting Star (bearish reversal)
        if (upper_wick(c3) >= 2 * body_size(c3) and 
            lower_wick(c3) <= 0.5 * body_size(c3) and
            c3.close < c3.open):
            patterns.append(CandlePattern.SHOOTING_STAR)
        
        # Bullish Engulfing
        if (c3.open < c2.close and c3.close > c2.open and
            c2.close < c2.open):
            patterns.append(CandlePattern.ENGULFING_BULLISH)
        
        # Bearish Engulfing
        if (c3.open > c2.close and c3.close < c2.open and
            c2.close > c2.open):
            patterns.append(CandlePattern.ENGULFING_BEARISH)
        
        # Doji
        if body_size(c3) <= 0.1 * (c3.high - c3.low):
            patterns.append(CandlePattern.DOJI)
        
        # Pin Bar
        if (upper_wick(c3) >= 2 * body_size(c3) or 
            lower_wick(c3) >= 2 * body_size(c3)):
            patterns.append(CandlePattern.PIN_BAR)
        
        # Inside Bar
        if (c3.high <= c2.high and c3.low >= c2.low):
            patterns.append(CandlePattern.INSIDE_BAR)
        
        # Outside Bar
        if (c3.high >= c2.high and c3.low <= c2.low):
            patterns.append(CandlePattern.OUTSIDE_BAR)
        
        # Morning Star (3-candle bullish reversal)
        if (c1.close < c1.open and c2.close > c2.open and
            c3.close > c2.close and c2.open < c1.close and
            c2.close > c1.close):
            patterns.append(CandlePattern.MORNING_STAR)
        
        # Evening Star (3-candle bearish reversal)
        if (c1.close > c1.open and c2.close < c2.open and
            c3.close < c2.close and c2.open > c1.close and
            c2.close < c1.close):
            patterns.append(CandlePattern.EVENING_STAR)
        
        return list(set(patterns))  # Remove duplicates
    
    def _find_support_resistance(
        self, 
        candles: List[Candle], 
        lookback: int = 100
    ) -> Tuple[List[SupportResistance], List[SupportResistance]]:
        """Find support and resistance levels"""
        if len(candles) < lookback:
            return [], []
        
        recent_candles = candles[-lookback:]
        highs = [c.high for c in recent_candles]
        lows = [c.low for c in recent_candles]
        
        support_levels = []
        resistance_levels = []
        
        # Find local minima (support) and maxima (resistance)
        for i in range(2, len(recent_candles) - 2):
            # Check for local minimum (support)
            if (lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and
                lows[i] <= lows[i+1] and lows[i] <= lows[i+2]):
                
                # Count touches
                touches = sum(1 for j in range(max(0, i-10), min(len(lows), i+11)) 
                           if abs(lows[j] - lows[i]) <= 0.001 * lows[i])
                
                strength = min(touches / 10, 1.0)
                
                support_levels.append(SupportResistance(
                    price=lows[i],
                    level_type="support",
                    strength=strength,
                    touches=touches,
                    last_touch=recent_candles[i].timestamp
                ))
            
            # Check for local maximum (resistance)
            if (highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and
                highs[i] >= highs[i+1] and highs[i] >= highs[i+2]):
                
                # Count touches
                touches = sum(1 for j in range(max(0, i-10), min(len(highs), i+11)) 
                           if abs(highs[j] - highs[i]) <= 0.001 * highs[i])
                
                strength = min(touches / 10, 1.0)
                
                resistance_levels.append(SupportResistance(
                    price=highs[i],
                    level_type="resistance",
                    strength=strength,
                    touches=touches,
                    last_touch=recent_candles[i].timestamp
                ))
        
        # Filter and sort
        support_levels = sorted(
            [s for s in support_levels if s.strength >= config.technical.SR_STRENGTH_THRESHOLD],
            key=lambda x: x.price,
            reverse=True
        )[:5]
        
        resistance_levels = sorted(
            [r for r in resistance_levels if r.strength >= config.technical.SR_STRENGTH_THRESHOLD],
            key=lambda x: x.price
        )[:5]
        
        return support_levels, resistance_levels
    
    def _analyze_trend(
        self, 
        prices: List[float], 
        period: int
    ) -> TrendInfo:
        """Analyze trend for a specific period"""
        if len(prices) < period:
            return TrendInfo(
                direction=TrendDirection.NEUTRAL,
                strength=0.0,
                duration=0,
                confidence=0.0
            )
        
        sma_short = self._calculate_sma(prices, period // 2)
        sma_long = self._calculate_sma(prices, period)
        
        if not sma_short or not sma_long:
            return TrendInfo(
                direction=TrendDirection.NEUTRAL,
                strength=0.0,
                duration=0,
                confidence=0.0
            )
        
        # Compare last values
        short_val = sma_short[-1]
        long_val = sma_long[-1]
        
        # Calculate slope
        if len(sma_long) >= 5:
            slope = sma_long[-1] - sma_long[-5]
        else:
            slope = 0
        
        # Determine direction and strength
        if short_val > long_val and slope > 0:
            direction = TrendDirection.STRONG_UP if short_val > long_val * 1.01 else TrendDirection.UP
            strength = min(abs(short_val - long_val) / long_val * 100, 1.0)
        elif short_val < long_val and slope < 0:
            direction = TrendDirection.STRONG_DOWN if long_val > short_val * 1.01 else TrendDirection.DOWN
            strength = min(abs(short_val - long_val) / long_val * 100, 1.0)
        else:
            direction = TrendDirection.NEUTRAL
            strength = 0.0
        
        # Calculate duration (consecutive candles in trend)
        duration = 0
        for i in range(len(sma_short) - 1, max(0, len(sma_short) - 50), -1):
            if (direction in [TrendDirection.STRONG_UP, TrendDirection.UP] and 
                sma_short[i] > sma_long[i]):
                duration += 1
            elif (direction in [TrendDirection.STRONG_DOWN, TrendDirection.DOWN] and 
                  sma_short[i] < sma_long[i]):
                duration += 1
            else:
                break
        
        confidence = min(strength * (duration / 50), 1.0)
        
        return TrendInfo(
            direction=direction,
            strength=strength,
            duration=duration,
            confidence=confidence
        )
    
    def _detect_breakout(
        self, 
        candles: List[Candle], 
        support_levels: List[SupportResistance],
        resistance_levels: List[SupportResistance]
    ) -> Tuple[bool, bool, Optional[float]]:
        """Detect breakout from support/resistance"""
        if not candles:
            return False, False, None
        
        current_price = candles[-1].close
        prev_price = candles[-2].close if len(candles) > 1 else current_price
        
        breakout_upper = False
        breakout_lower = False
        breakout_price = None
        
        # Check resistance breakout
        for level in resistance_levels:
            if prev_price <= level.price and current_price > level.price:
                breakout_upper = True
                breakout_price = level.price
                break
        
        # Check support breakout
        for level in support_levels:
            if prev_price >= level.price and current_price < level.price:
                breakout_lower = True
                breakout_price = level.price
                break
        
        return breakout_upper, breakout_lower, breakout_price
    
    def _detect_reversal(
        self, 
        candles: List[Candle],
        trend_info: TrendInfo
    ) -> Tuple[bool, bool, float]:
        """Detect potential trend reversal"""
        if len(candles) < 5:
            return False, False, 0.0
        
        current_price = candles[-1].close
        prices = [c.close for c in candles[-5:]]
        
        # Check for reversal signals
        potential_up = False
        potential_down = False
        strength = 0.0
        
        # If current trend is down, look for bullish reversal
        if trend_info.direction in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]:
            # Check for bullish divergence
            if current_price > prices[-2] and prices[-2] > prices[-3]:
                potential_up = True
                strength = 0.7
            
            # Check for hammer or bullish engulfing
            patterns = self._detect_candle_patterns(candles[-3:])
            if CandlePattern.HAMMER in patterns or CandlePattern.ENGULFING_BULLISH in patterns:
                potential_up = True
                strength = max(strength, 0.8)
        
        # If current trend is up, look for bearish reversal
        elif trend_info.direction in [TrendDirection.UP, TrendDirection.STRONG_UP]:
            # Check for bearish divergence
            if current_price < prices[-2] and prices[-2] < prices[-3]:
                potential_down = True
                strength = 0.7
            
            # Check for shooting star or bearish engulfing
            patterns = self._detect_candle_patterns(candles[-3:])
            if CandlePattern.SHOOTING_STAR in patterns or CandlePattern.ENGULFING_BEARISH in patterns:
                potential_down = True
                strength = max(strength, 0.8)
        
        return potential_up, potential_down, strength
    
    def _calculate_overall_signal(
        self, 
        analysis: AnalysisResult
    ) -> Tuple[SignalType, float, float]:
        """Calculate overall trading signal from all indicators"""
        score = 0.0
        confidence = 0.0
        
        # Trend-based scoring
        trend_scores = {
            TrendDirection.STRONG_UP: 2.0,
            TrendDirection.UP: 1.0,
            TrendDirection.NEUTRAL: 0.0,
            TrendDirection.DOWN: -1.0,
            TrendDirection.STRONG_DOWN: -2.0
        }
        
        # Weight short-term trend more heavily
        if analysis.short_term_trend:
            score += trend_scores[analysis.short_term_trend.direction] * 0.4
            confidence += analysis.short_term_trend.confidence * 0.4
        
        if analysis.medium_term_trend:
            score += trend_scores[analysis.medium_term_trend.direction] * 0.35
            confidence += analysis.medium_term_trend.confidence * 0.35
        
        if analysis.long_term_trend:
            score += trend_scores[analysis.long_term_trend.direction] * 0.25
            confidence += analysis.long_term_trend.confidence * 0.25
        
        # RSI signal
        rsi = analysis.indicators.get("RSI")
        if rsi:
            rsi_val = rsi.value
            if rsi_val < 30:
                score += 1.5  # Oversold
                confidence += 0.8
            elif rsi_val > 70:
                score -= 1.5  # Overbought
                confidence += 0.8
            elif rsi_val < 40:
                score += 0.5
            elif rsi_val > 60:
                score -= 0.5
        
        # MACD signal
        macd = analysis.indicators.get("MACD")
        macd_signal = analysis.indicators.get("MACD_Signal")
        macd_hist = analysis.indicators.get("MACD_Histogram")
        
        if macd and macd_signal and macd_hist:
            if macd.value > macd_signal.value and macd_hist.value > 0:
                score += 1.0
                confidence += 0.7
            elif macd.value < macd_signal.value and macd_hist.value < 0:
                score -= 1.0
                confidence += 0.7
        
        # Bollinger Bands
        bb_upper = analysis.indicators.get("BB_Upper")
        bb_lower = analysis.indicators.get("BB_Lower")
        
        if bb_upper and bb_lower:
            price = analysis.current_price
            if price > bb_upper.value:
                score -= 0.5  # Price above upper band
            elif price < bb_lower.value:
                score += 0.5  # Price below lower band
        
        # Stochastic
        stoch_k = analysis.indicators.get("Stochastic_K")
        stoch_d = analysis.indicators.get("Stochastic_D")
        
        if stoch_k and stoch_d:
            if stoch_k.value < 20 and stoch_k.value > stoch_d.value:
                score += 1.0  # Oversold with crossover
            elif stoch_k.value > 80 and stoch_k.value < stoch_d.value:
                score -= 1.0  # Overbought with crossover
        
        # Volume spike
        if analysis.volume_spike:
            if score > 0:
                score *= 1.2  # Boost signal with volume confirmation
            elif score < 0:
                score *= 1.2
        
        # Breakout detection
        if analysis.breakout_upper:
            score += 1.5
            confidence += 0.8
        elif analysis.breakout_lower:
            score -= 1.5
            confidence += 0.8
        
        # Reversal detection
        if analysis.potential_reversal_up:
            score += analysis.reversal_strength * 1.5
            confidence += analysis.reversal_strength * 0.5
        elif analysis.potential_reversal_down:
            score -= analysis.reversal_strength * 1.5
            confidence += analysis.reversal_strength * 0.5
        
        # Candle patterns
        pattern_scores = {
            CandlePattern.HAMMER: 1.5,
            CandlePattern.ENGULFING_BULLISH: 1.5,
            CandlePattern.MORNING_STAR: 2.0,
            CandlePattern.SHOOTING_STAR: -1.5,
            CandlePattern.ENGULFING_BEARISH: -1.5,
            CandlePattern.EVENING_STAR: -2.0,
            CandlePattern.PIN_BAR: 0.5,
            CandlePattern.OUTSIDE_BAR: 1.0,
            CandlePattern.INSIDE_BAR: -0.5
        }
        
        for pattern in analysis.candle_patterns:
            if pattern in pattern_scores:
                score += pattern_scores[pattern]
                confidence += 0.3
        
        # Normalize confidence
        confidence = min(confidence, 1.0)
        
        # Determine signal type
        if score >= 2.5:
            signal = SignalType.STRONG_BUY
        elif score >= 1.5:
            signal = SignalType.BUY
        elif score >= 0.5:
            signal = SignalType.WEAK_BUY
        elif score <= -2.5:
            signal = SignalType.STRONG_SELL
        elif score <= -1.5:
            signal = SignalType.SELL
        elif score <= -0.5:
            signal = SignalType.WEAK_SELL
        else:
            signal = SignalType.NEUTRAL
        
        # Normalize signal strength
        signal_strength = min(abs(score) / 3.0, 1.0)
        
        return signal, signal_strength, confidence
    
    def analyze(self, candles: List[Candle], timeframe: str = "1m") -> AnalysisResult:
        """Perform comprehensive technical analysis"""
        if not candles:
            raise ValueError("No candle data provided")
        
        current_candle = candles[-1]
        prices = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        
        # Calculate indicators
        indicators = {}
        
        # Moving Averages
        for period in [5, 10, 20, 50, 100, 200]:
            sma = self._calculate_sma(prices, period)
            if sma:
                indicators[f"SMA_{period}"] = IndicatorValue(name=f"SMA_{period}", value=sma[-1])
        
        for period in [5, 10, 20, 50]:
            ema = self._calculate_ema(prices, period)
            if ema:
                indicators[f"EMA_{period}"] = IndicatorValue(name=f"EMA_{period}", value=ema[-1])
        
        # RSI
        rsi = self._calculate_rsi(prices, 14)
        if rsi:
            indicators["RSI"] = IndicatorValue(name="RSI", value=rsi[-1])
        
        # MACD
        macd_line, signal_line, histogram = self._calculate_macd(prices, 12, 26, 9)
        if macd_line:
            indicators["MACD"] = IndicatorValue(name="MACD", value=macd_line[-1])
        if signal_line:
            indicators["MACD_Signal"] = IndicatorValue(name="MACD_Signal", value=signal_line[-1])
        if histogram:
            indicators["MACD_Histogram"] = IndicatorValue(name="MACD_Histogram", value=histogram[-1])
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(prices, 20, 2.0)
        if bb_upper:
            indicators["BB_Upper"] = IndicatorValue(name="BB_Upper", value=bb_upper[-1])
        if bb_middle:
            indicators["BB_Middle"] = IndicatorValue(name="BB_Middle", value=bb_middle[-1])
        if bb_lower:
            indicators["BB_Lower"] = IndicatorValue(name="BB_Lower", value=bb_lower[-1])
        
        # Stochastic
        stoch_k, stoch_d = self._calculate_stochastic(highs, lows, prices, 14, 3)
        if stoch_k:
            indicators["Stochastic_K"] = IndicatorValue(name="Stochastic_K", value=stoch_k[-1])
        if stoch_d:
            indicators["Stochastic_D"] = IndicatorValue(name="Stochastic_D", value=stoch_d[-1])
        
        # ATR
        atr = self._calculate_atr(highs, lows, prices, 14)
        if atr:
            indicators["ATR"] = IndicatorValue(name="ATR", value=atr[-1])
        
        # Volume indicators
        volume_data = self._calculate_volume_indicators(volumes, prices)
        for key, value in volume_data.items():
            indicators[key] = IndicatorValue(name=key, value=value)
        
        # Trend analysis
        short_trend = self._analyze_trend(prices, self.lookback_periods["short"])
        medium_trend = self._analyze_trend(prices, self.lookback_periods["medium"])
        long_trend = self._analyze_trend(prices, self.lookback_periods["long"])
        
        # Support and Resistance
        support_levels, resistance_levels = self._find_support_resistance(
            candles, config.technical.SR_LOOKBACK_PERIODS
        )
        
        # Candle patterns
        candle_patterns = self._detect_candle_patterns(candles)
        
        # Breakout detection
        breakout_upper, breakout_lower, breakout_price = self._detect_breakout(
            candles, support_levels, resistance_levels
        )
        
        # Reversal detection (use medium term trend)
        potential_reversal_up, potential_reversal_down, reversal_strength = self._detect_reversal(
            candles, medium_trend
        )
        
        # Volume spike detection
        volume_ratio = volume_data.get("volume_ratio", 0)
        volume_spike = volume_ratio > config.technical.VOLUME_SPIKE_THRESHOLD
        
        # Create analysis result
        result = AnalysisResult(
            timestamp=current_candle.timestamp,
            timeframe=timeframe,
            current_price=current_candle.close,
            high=current_candle.high,
            low=current_candle.low,
            indicators=indicators,
            short_term_trend=short_trend,
            medium_term_trend=medium_trend,
            long_term_trend=long_trend,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            candle_patterns=candle_patterns,
            volume=current_candle.volume,
            volume_spike=volume_spike,
            breakout_upper=breakout_upper,
            breakout_lower=breakout_lower,
            breakout_price=breakout_price,
            potential_reversal_up=potential_reversal_up,
            potential_reversal_down=potential_reversal_down,
            reversal_strength=reversal_strength
        )
        
        # Calculate overall signal
        overall_signal, signal_strength, signal_confidence = self._calculate_overall_signal(result)
        
        result.overall_signal = overall_signal
        result.signal_strength = signal_strength
        result.signal_confidence = signal_confidence
        
        return result
    
    def analyze_multiple_timeframes(
        self, 
        candles_dict: Dict[str, List[Candle]]
    ) -> Dict[str, AnalysisResult]:
        """Analyze multiple timeframes"""
        results = {}
        
        for timeframe, candles in candles_dict.items():
            try:
                results[timeframe] = self.analyze(candles, timeframe)
            except Exception as e:
                logger.error(f"Failed to analyze {timeframe}: {e}")
                results[timeframe] = None
        
        return results


# Global instance
technical_analyzer = TechnicalAnalyzer()


if __name__ == "__main__":
    # Test the analyzer
    from .data_fetcher import BIQuoteClient
    import asyncio
    
    async def test():
        async with BIQuoteClient() as client:
            candles = await client.get_historical_candles("1m", 200)
            
            analyzer = TechnicalAnalyzer()
            result = analyzer.analyze(candles, "1m")
            
            print(f"Analysis for {result.timestamp}")
            print(f"Current Price: {result.current_price}")
            print(f"Overall Signal: {result.overall_signal.value}")
            print(f"Signal Strength: {result.signal_strength:.2f}")
            print(f"Signal Confidence: {result.signal_confidence:.2f}")
            print(f"Candle Patterns: {[p.value for p in result.candle_patterns]}")
            print(f"Support Levels: {[s.price for s in result.support_levels]}")
            print(f"Resistance Levels: {[r.price for r in result.resistance_levels]}")
            
            print("\nKey Indicators:")
            for name in ["RSI", "MACD", "MACD_Signal", "MACD_Histogram"]:
                if name in result.indicators:
                    print(f"  {name}: {result.indicators[name].value:.4f}")
    
    asyncio.run(test())

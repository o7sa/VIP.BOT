"""
Pattern Detector Module - Advanced pattern recognition for XAUUSD
Detects peaks, valleys, breakouts, and complex chart patterns
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


class PatternType(Enum):
    """Types of chart patterns"""
    # Peaks and Valleys
    PEAK = "PEAK"
    VALLEY = "VALLEY"
    HIGHER_HIGH = "HIGHER_HIGH"
    LOWER_LOW = "LOWER_LOW"
    DOUBLE_TOP = "DOUBLE_TOP"
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"
    TRIPLE_TOP = "TRIPLE_TOP"
    TRIPLE_BOTTOM = "TRIPLE_BOTTOM"
    
    # Trend Patterns
    ASCENDING_TRENDLINE = "ASCENDING_TRENDLINE"
    DESCENDING_TRENDLINE = "DESCENDING_TRENDLINE"
    TRENDLINE_BREAK = "TRENDLINE_BREAK"
    
    # Continuation Patterns
    FLAG = "FLAG"
    PENNANT = "PENNANT"
    WEDGE_ASCENDING = "WEDGE_ASCENDING"
    WEDGE_DESCENDING = "WEDGE_DESCENDING"
    RECTANGLE = "RECTANGLE"
    
    # Reversal Patterns
    HEAD_AND_SHOULDERS = "HEAD_AND_SHOULDERS"
    INVERSE_HEAD_AND_SHOULDERS = "INVERSE_HEAD_AND_SHOULDERS"
    
    # Breakout Patterns
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"
    
    # Volume Patterns
    VOLUME_SPIKE = "VOLUME_SPIKE"
    VOLUME_DROPOFF = "VOLUME_DROPOFF"
    VOLUME_DIVERGENCE = "VOLUME_DIVERGENCE"


@dataclass
class Pattern:
    """Represents a detected pattern"""
    pattern_type: PatternType
    name: str
    start_index: int
    end_index: int
    start_time: datetime
    end_time: datetime
    price_level: float
    strength: float  # 0-1
    confidence: float  # 0-1
    confirmed: bool
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.pattern_type.value,
            "name": self.name,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "price_level": self.price_level,
            "strength": self.strength,
            "confidence": self.confidence,
            "confirmed": self.confirmed,
            "description": self.description
        }


@dataclass
class PeakValley:
    """Represents a peak or valley"""
    index: int
    timestamp: datetime
    price: float
    pattern_type: PatternType  # PEAK or VALLEY
    strength: float
    confirmed: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "type": self.pattern_type.value,
            "strength": self.strength,
            "confirmed": self.confirmed
        }


class PatternDetector:
    """Advanced Pattern Detector for XAUUSD"""
    
    def __init__(self):
        self.peak_threshold = 0.005  # 0.5% price change
        self.valley_threshold = 0.005
        self.min_peak_distance = 5  # Minimum candles between peaks
        
    def _find_peaks_and_valleys(
        self, 
        candles: List[Candle], 
        lookback: int = 100
    ) -> Tuple[List[PeakValley], List[PeakValley]]:
        """Find peaks and valleys using local maxima/minima detection"""
        if len(candles) < lookback:
            return [], []
        
        prices = [c.close for c in candles]
        peaks = []
        valleys = []
        
        # Find local maxima (peaks)
        for i in range(2, len(prices) - 2):
            window = prices[i-2:i+3]
            if prices[i] == max(window):
                # Check if it's a significant peak
                left_diff = (prices[i] - prices[i-2]) / prices[i-2] if prices[i-2] > 0 else 0
                right_diff = (prices[i] - prices[i+2]) / prices[i+2] if prices[i+2] > 0 else 0
                
                if left_diff >= self.peak_threshold and right_diff >= self.peak_threshold:
                    strength = min((left_diff + right_diff) / 0.02, 1.0)  # Normalize
                    peaks.append(PeakValley(
                        index=i,
                        timestamp=candles[i].timestamp,
                        price=prices[i],
                        pattern_type=PatternType.PEAK,
                        strength=strength,
                        confirmed=False
                    ))
        
        # Find local minima (valleys)
        for i in range(2, len(prices) - 2):
            window = prices[i-2:i+3]
            if prices[i] == min(window):
                # Check if it's a significant valley
                left_diff = (prices[i-2] - prices[i]) / prices[i-2] if prices[i-2] > 0 else 0
                right_diff = (prices[i+2] - prices[i]) / prices[i+2] if prices[i+2] > 0 else 0
                
                if left_diff >= self.valley_threshold and right_diff >= self.valley_threshold:
                    strength = min((left_diff + right_diff) / 0.02, 1.0)
                    valleys.append(PeakValley(
                        index=i,
                        timestamp=candles[i].timestamp,
                        price=prices[i],
                        pattern_type=PatternType.VALLEY,
                        strength=strength,
                        confirmed=False
                    ))
        
        # Filter peaks and valleys that are too close
        peaks = self._filter_close_patterns(peaks)
        valleys = self._filter_close_patterns(valleys)
        
        return peaks, valleys
    
    def _filter_close_patterns(self, patterns: List[PeakValley]) -> List[PeakValley]:
        """Filter patterns that are too close to each other"""
        if not patterns:
            return []
        
        filtered = [patterns[0]]
        for i in range(1, len(patterns)):
            if patterns[i].index - filtered[-1].index >= self.min_peak_distance:
                filtered.append(patterns[i])
            elif patterns[i].strength > filtered[-1].strength:
                # Replace with stronger pattern
                filtered[-1] = patterns[i]
        
        return filtered
    
    def _detect_double_top_bottom(
        self, 
        peaks: List[PeakValley], 
        valleys: List[PeakValley]
    ) -> List[Pattern]:
        """Detect double top and double bottom patterns"""
        patterns = []
        
        # Double Top detection
        for i in range(len(peaks) - 1):
            p1, p2 = peaks[i], peaks[i+1]
            
            # Check if prices are close (within 0.5%)
            price_diff = abs(p1.price - p2.price) / p1.price
            
            # Check if there's a valley between them
            valley_between = any(
                p1.index < v.index < p2.index 
                for v in valleys
            )
            
            if price_diff <= 0.005 and valley_between:
                # Calculate neckline (lowest point between peaks)
                neckline_price = min(
                    c.low for c in [peaks[i].candle, peaks[i+1].candle]
                    if hasattr(peaks[i], 'candle')
                )
                
                strength = min((p1.strength + p2.strength) / 2, 1.0)
                confidence = 0.7 + (0.3 if abs(p1.price - p2.price) / p1.price < 0.002 else 0)
                
                patterns.append(Pattern(
                    pattern_type=PatternType.DOUBLE_TOP,
                    name="Double Top",
                    start_index=peaks[i].index,
                    end_index=peaks[i+1].index,
                    start_time=peaks[i].timestamp,
                    end_time=peaks[i+1].timestamp,
                    price_level=neckline_price,
                    strength=strength,
                    confidence=confidence,
                    confirmed=False,
                    description=f"Double top at {p1.price:.2f} and {p2.price:.2f}"
                ))
        
        # Double Bottom detection
        for i in range(len(valleys) - 1):
            v1, v2 = valleys[i], valleys[i+1]
            
            price_diff = abs(v1.price - v2.price) / v1.price
            
            peak_between = any(
                v1.index < p.index < v2.index 
                for p in peaks
            )
            
            if price_diff <= 0.005 and peak_between:
                neckline_price = max(
                    c.high for c in [valleys[i].candle, valleys[i+1].candle]
                    if hasattr(valleys[i], 'candle')
                )
                
                strength = min((v1.strength + v2.strength) / 2, 1.0)
                confidence = 0.7 + (0.3 if abs(v1.price - v2.price) / v1.price < 0.002 else 0)
                
                patterns.append(Pattern(
                    pattern_type=PatternType.DOUBLE_BOTTOM,
                    name="Double Bottom",
                    start_index=valleys[i].index,
                    end_index=valleys[i+1].index,
                    start_time=valleys[i].timestamp,
                    end_time=valleys[i+1].timestamp,
                    price_level=neckline_price,
                    strength=strength,
                    confidence=confidence,
                    confirmed=False,
                    description=f"Double bottom at {v1.price:.2f} and {v2.price:.2f}"
                ))
        
        return patterns
    
    def _detect_triple_top_bottom(
        self, 
        peaks: List[PeakValley], 
        valleys: List[PeakValley]
    ) -> List[Pattern]:
        """Detect triple top and triple bottom patterns"""
        patterns = []
        
        # Triple Top detection
        for i in range(len(peaks) - 2):
            p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
            
            avg_price = (p1.price + p2.price + p3.price) / 3
            price_diffs = [abs(p.price - avg_price) / avg_price for p in [p1, p2, p3]]
            
            # Check if all prices are close (within 0.5%)
            if all(diff <= 0.005 for diff in price_diffs):
                # Check for valleys between peaks
                valley_count = sum(
                    1 for v in valleys if p1.index < v.index < p3.index
                )
                
                if valley_count >= 2:
                    neckline_price = min(c.low for c in [p1, p2, p3] if hasattr(p, 'candle'))
                    
                    strength = min(sum(p.strength for p in [p1, p2, p3]) / 3, 1.0)
                    confidence = 0.6 + (0.4 if max(price_diffs) < 0.002 else 0)
                    
                    patterns.append(Pattern(
                        pattern_type=PatternType.TRIPLE_TOP,
                        name="Triple Top",
                        start_index=p1.index,
                        end_index=p3.index,
                        start_time=p1.timestamp,
                        end_time=p3.timestamp,
                        price_level=neckline_price,
                        strength=strength,
                        confidence=confidence,
                        confirmed=False,
                        description=f"Triple top at {avg_price:.2f}"
                    ))
        
        # Triple Bottom detection
        for i in range(len(valleys) - 2):
            v1, v2, v3 = valleys[i], valleys[i+1], valleys[i+2]
            
            avg_price = (v1.price + v2.price + v3.price) / 3
            price_diffs = [abs(v.price - avg_price) / avg_price for v in [v1, v2, v3]]
            
            if all(diff <= 0.005 for diff in price_diffs):
                peak_count = sum(
                    1 for p in peaks if v1.index < p.index < v3.index
                )
                
                if peak_count >= 2:
                    neckline_price = max(c.high for c in [v1, v2, v3] if hasattr(v, 'candle'))
                    
                    strength = min(sum(v.strength for v in [v1, v2, v3]) / 3, 1.0)
                    confidence = 0.6 + (0.4 if max(price_diffs) < 0.002 else 0)
                    
                    patterns.append(Pattern(
                        pattern_type=PatternType.TRIPLE_BOTTOM,
                        name="Triple Bottom",
                        start_index=v1.index,
                        end_index=v3.index,
                        start_time=v1.timestamp,
                        end_time=v3.timestamp,
                        price_level=neckline_price,
                        strength=strength,
                        confidence=confidence,
                        confirmed=False,
                        description=f"Triple bottom at {avg_price:.2f}"
                    ))
        
        return patterns
    
    def _detect_trendlines(
        self, 
        candles: List[Candle], 
        peaks: List[PeakValley], 
        valleys: List[PeakValley]
    ) -> List[Pattern]:
        """Detect trendlines and breakouts"""
        patterns = []
        
        if len(peaks) >= 2:
            # Check for descending trendline (connecting peaks)
            p1, p2 = peaks[-2], peaks[-1]
            
            if p2.index > p1.index and p2.price < p1.price:
                # Check if current price is below trendline
                current_price = candles[-1].close
                trendline_price = self._calculate_trendline_price(
                    p1.index, p1.price, p2.index, p2.price, len(candles) - 1
                )
                
                if current_price < trendline_price:
                    # Trendline break down
                    strength = min((p1.price - p2.price) / p1.price * 10, 1.0)
                    patterns.append(Pattern(
                        pattern_type=PatternType.TRENDLINE_BREAK,
                        name="Descending Trendline Break",
                        start_index=p1.index,
                        end_index=p2.index,
                        start_time=p1.timestamp,
                        end_time=p2.timestamp,
                        price_level=trendline_price,
                        strength=strength,
                        confidence=0.8,
                        confirmed=True,
                        description=f"Price broke below descending trendline at {trendline_price:.2f}"
                    ))
        
        if len(valleys) >= 2:
            # Check for ascending trendline (connecting valleys)
            v1, v2 = valleys[-2], valleys[-1]
            
            if v2.index > v1.index and v2.price > v1.price:
                current_price = candles[-1].close
                trendline_price = self._calculate_trendline_price(
                    v1.index, v1.price, v2.index, v2.price, len(candles) - 1
                )
                
                if current_price > trendline_price:
                    # Trendline break up
                    strength = min((v2.price - v1.price) / v1.price * 10, 1.0)
                    patterns.append(Pattern(
                        pattern_type=PatternType.TRENDLINE_BREAK,
                        name="Ascending Trendline Break",
                        start_index=v1.index,
                        end_index=v2.index,
                        start_time=v1.timestamp,
                        end_time=v2.timestamp,
                        price_level=trendline_price,
                        strength=strength,
                        confidence=0.8,
                        confirmed=True,
                        description=f"Price broke above ascending trendline at {trendline_price:.2f}"
                    ))
        
        return patterns
    
    def _calculate_trendline_price(
        self, 
        x1: int, y1: float, 
        x2: int, y2: float, 
        x: int
    ) -> float:
        """Calculate trendline price at position x"""
        if x2 == x1:
            return y1
        
        slope = (y2 - y1) / (x2 - x1)
        return y1 + slope * (x - x1)
    
    def _detect_head_and_shoulders(
        self, 
        candles: List[Candle], 
        peaks: List[PeakValley], 
        valleys: List[PeakValley]
    ) -> List[Pattern]:
        """Detect Head and Shoulders and Inverse Head and Shoulders patterns"""
        patterns = []
        
        if len(peaks) < 3:
            return patterns
        
        # Head and Shoulders (bearish reversal)
        for i in range(1, len(peaks) - 1):
            left_shoulder = peaks[i-1]
            head = peaks[i]
            right_shoulder = peaks[i+1]
            
            # Check if head is higher than shoulders
            if (head.price > left_shoulder.price * 1.01 and 
                head.price > right_shoulder.price * 1.01):
                
                # Check if shoulders are at similar level
                shoulder_diff = abs(left_shoulder.price - right_shoulder.price) / left_shoulder.price
                
                if shoulder_diff <= 0.01:  # 1% difference
                    # Find neckline (lowest valley between left shoulder and head)
                    neckline_valley = None
                    for v in valleys:
                        if left_shoulder.index < v.index < head.index:
                            neckline_valley = v
                            break
                    
                    if neckline_valley:
                        neckline_price = neckline_valley.price
                        
                        # Check if price broke below neckline
                        current_price = candles[-1].close
                        
                        strength = min((head.price - left_shoulder.price) / left_shoulder.price * 5, 1.0)
                        confidence = 0.7 + (0.3 if shoulder_diff < 0.005 else 0)
                        
                        patterns.append(Pattern(
                            pattern_type=PatternType.HEAD_AND_SHOULDERS,
                            name="Head and Shoulders",
                            start_index=left_shoulder.index,
                            end_index=right_shoulder.index,
                            start_time=left_shoulder.timestamp,
                            end_time=right_shoulder.timestamp,
                            price_level=neckline_price,
                            strength=strength,
                            confidence=confidence,
                            confirmed=current_price < neckline_price,
                            description=f"Head and Shoulders with neckline at {neckline_price:.2f}"
                        ))
        
        # Inverse Head and Shoulders (bullish reversal)
        if len(valleys) < 3:
            return patterns
        
        for i in range(1, len(valleys) - 1):
            left_shoulder = valleys[i-1]
            head = valleys[i]
            right_shoulder = valleys[i+1]
            
            if (head.price < left_shoulder.price * 0.99 and 
                head.price < right_shoulder.price * 0.99):
                
                shoulder_diff = abs(left_shoulder.price - right_shoulder.price) / left_shoulder.price
                
                if shoulder_diff <= 0.01:
                    # Find neckline (highest peak between left shoulder and head)
                    neckline_peak = None
                    for p in peaks:
                        if left_shoulder.index < p.index < head.index:
                            neckline_peak = p
                            break
                    
                    if neckline_peak:
                        neckline_price = neckline_peak.price
                        current_price = candles[-1].close
                        
                        strength = min((left_shoulder.price - head.price) / left_shoulder.price * 5, 1.0)
                        confidence = 0.7 + (0.3 if shoulder_diff < 0.005 else 0)
                        
                        patterns.append(Pattern(
                            pattern_type=PatternType.INVERSE_HEAD_AND_SHOULDERS,
                            name="Inverse Head and Shoulders",
                            start_index=left_shoulder.index,
                            end_index=right_shoulder.index,
                            start_time=left_shoulder.timestamp,
                            end_time=right_shoulder.timestamp,
                            price_level=neckline_price,
                            strength=strength,
                            confidence=confidence,
                            confirmed=current_price > neckline_price,
                            description=f"Inverse H&S with neckline at {neckline_price:.2f}"
                        ))
        
        return patterns
    
    def _detect_breakouts(
        self, 
        candles: List[Candle], 
        support_levels: List[float], 
        resistance_levels: List[float]
    ) -> List[Pattern]:
        """Detect breakouts from support/resistance"""
        patterns = []
        
        if len(candles) < 2:
            return patterns
        
        current_price = candles[-1].close
        prev_price = candles[-2].close
        
        # Check for breakout up
        for level in resistance_levels:
            if prev_price <= level and current_price > level:
                strength = min((current_price - level) / level * 10, 1.0)
                patterns.append(Pattern(
                    pattern_type=PatternType.BREAKOUT_UP,
                    name="Breakout Up",
                    start_index=len(candles) - 2,
                    end_index=len(candles) - 1,
                    start_time=candles[-2].timestamp,
                    end_time=candles[-1].timestamp,
                    price_level=level,
                    strength=strength,
                    confidence=0.8,
                    confirmed=True,
                    description=f"Broke above resistance at {level:.2f}"
                ))
        
        # Check for breakout down
        for level in support_levels:
            if prev_price >= level and current_price < level:
                strength = min((level - current_price) / level * 10, 1.0)
                patterns.append(Pattern(
                    pattern_type=PatternType.BREAKOUT_DOWN,
                    name="Breakout Down",
                    start_index=len(candles) - 2,
                    end_index=len(candles) - 1,
                    start_time=candles[-2].timestamp,
                    end_time=candles[-1].timestamp,
                    price_level=level,
                    strength=strength,
                    confidence=0.8,
                    confirmed=True,
                    description=f"Broke below support at {level:.2f}"
                ))
        
        return patterns
    
    def _detect_volume_patterns(
        self, 
        candles: List[Candle]
    ) -> List[Pattern]:
        """Detect volume-based patterns"""
        patterns = []
        
        if len(candles) < 20:
            return patterns
        
        volumes = [c.volume for c in candles]
        prices = [c.close for c in candles]
        
        avg_volume_20 = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]
        
        # Volume spike
        if current_volume > avg_volume_20 * config.technical.VOLUME_SPIKE_THRESHOLD:
            strength = min(current_volume / avg_volume_20 / 2, 1.0)
            patterns.append(Pattern(
                pattern_type=PatternType.VOLUME_SPIKE,
                name="Volume Spike",
                start_index=len(candles) - 1,
                end_index=len(candles) - 1,
                start_time=candles[-1].timestamp,
                end_time=candles[-1].timestamp,
                price_level=prices[-1],
                strength=strength,
                confidence=0.9,
                confirmed=True,
                description=f"Volume spike: {current_volume:.0f} vs avg {avg_volume_20:.0f}"
            ))
        
        # Volume dropoff
        if current_volume < avg_volume_20 * 0.5:
            patterns.append(Pattern(
                pattern_type=PatternType.VOLUME_DROPOFF,
                name="Volume Dropoff",
                start_index=len(candles) - 1,
                end_index=len(candles) - 1,
                start_time=candles[-1].timestamp,
                end_time=candles[-1].timestamp,
                price_level=prices[-1],
                strength=min((avg_volume_20 - current_volume) / avg_volume_20, 1.0),
                confidence=0.7,
                confirmed=True,
                description=f"Volume dropoff: {current_volume:.0f} vs avg {avg_volume_20:.0f}"
            ))
        
        return patterns
    
    def _identify_higher_highs_lower_lows(
        self, 
        peaks: List[PeakValley], 
        valleys: List[PeakValley]
    ) -> List[Pattern]:
        """Identify higher highs and lower lows for trend confirmation"""
        patterns = []
        
        # Higher Highs
        for i in range(1, len(peaks)):
            if peaks[i].price > peaks[i-1].price * 1.005:  # 0.5% higher
                patterns.append(Pattern(
                    pattern_type=PatternType.HIGHER_HIGH,
                    name="Higher High",
                    start_index=peaks[i-1].index,
                    end_index=peaks[i].index,
                    start_time=peaks[i-1].timestamp,
                    end_time=peaks[i].timestamp,
                    price_level=peaks[i].price,
                    strength=min((peaks[i].price - peaks[i-1].price) / peaks[i-1].price * 10, 1.0),
                    confidence=0.8,
                    confirmed=True,
                    description=f"Higher high: {peaks[i-1].price:.2f} -> {peaks[i].price:.2f}"
                ))
        
        # Lower Lows
        for i in range(1, len(valleys)):
            if valleys[i].price < valleys[i-1].price * 0.995:  # 0.5% lower
                patterns.append(Pattern(
                    pattern_type=PatternType.LOWER_LOW,
                    name="Lower Low",
                    start_index=valleys[i-1].index,
                    end_index=valleys[i].index,
                    start_time=valleys[i-1].timestamp,
                    end_time=valleys[i].timestamp,
                    price_level=valleys[i].price,
                    strength=min((valleys[i-1].price - valleys[i].price) / valleys[i-1].price * 10, 1.0),
                    confidence=0.8,
                    confirmed=True,
                    description=f"Lower low: {valleys[i-1].price:.2f} -> {valleys[i].price:.2f}"
                ))
        
        return patterns
    
    def detect_all_patterns(
        self, 
        candles: List[Candle], 
        support_levels: List[float] = None,
        resistance_levels: List[float] = None
    ) -> Dict[PatternType, List[Pattern]]:
        """Detect all patterns in the candle data"""
        if not candles:
            return {}
        
        # Initialize result dictionary
        all_patterns: Dict[PatternType, List[Pattern]] = {p: [] for p in PatternType}
        
        # Find peaks and valleys
        peaks, valleys = self._find_peaks_and_valleys(candles)
        
        # Detect patterns
        double_patterns = self._detect_double_top_bottom(peaks, valleys)
        for p in double_patterns:
            all_patterns[p.pattern_type].append(p)
        
        triple_patterns = self._detect_triple_top_bottom(peaks, valleys)
        for p in triple_patterns:
            all_patterns[p.pattern_type].append(p)
        
        trendline_patterns = self._detect_trendlines(candles, peaks, valleys)
        for p in trendline_patterns:
            all_patterns[p.pattern_type].append(p)
        
        hs_patterns = self._detect_head_and_shoulders(candles, peaks, valleys)
        for p in hs_patterns:
            all_patterns[p.pattern_type].append(p)
        
        # Breakout detection
        if support_levels is None:
            support_levels = []
        if resistance_levels is None:
            resistance_levels = []
        
        breakout_patterns = self._detect_breakouts(candles, support_levels, resistance_levels)
        for p in breakout_patterns:
            all_patterns[p.pattern_type].append(p)
        
        # Volume patterns
        volume_patterns = self._detect_volume_patterns(candles)
        for p in volume_patterns:
            all_patterns[p.pattern_type].append(p)
        
        # Higher highs and lower lows
        hhll_patterns = self._identify_higher_highs_lower_lows(peaks, valleys)
        for p in hhll_patterns:
            all_patterns[p.pattern_type].append(p)
        
        # Add peaks and valleys
        for p in peaks:
            all_patterns[PatternType.PEAK].append(p)
        for v in valleys:
            all_patterns[PatternType.VALLEY].append(v)
        
        # Sort patterns by strength
        for pattern_type in all_patterns:
            all_patterns[pattern_type].sort(key=lambda x: x.strength, reverse=True)
        
        return all_patterns
    
    def get_recent_patterns(
        self, 
        candles: List[Candle], 
        lookback_candles: int = 50
    ) -> List[Pattern]:
        """Get patterns from recent candles only"""
        if len(candles) > lookback_candles:
            recent_candles = candles[-lookback_candles:]
        else:
            recent_candles = candles
        
        all_patterns = self.detect_all_patterns(recent_candles)
        
        # Flatten all patterns and sort by end index (most recent first)
        recent = []
        for pattern_list in all_patterns.values():
            recent.extend(pattern_list)
        
        recent.sort(key=lambda x: x.end_index, reverse=True)
        
        return recent[:20]  # Return top 20 most recent patterns


# Global instance
pattern_detector = PatternDetector()


if __name__ == "__main__":
    # Test the pattern detector
    from .data_fetcher import BIQuoteClient
    import asyncio
    
    async def test():
        async with BIQuoteClient() as client:
            candles = await client.get_historical_candles("1m", 500)
            
            detector = PatternDetector()
            patterns = detector.detect_all_patterns(candles)
            
            print("Detected Patterns:")
            for pattern_type, pattern_list in patterns.items():
                if pattern_list:
                    print(f"\n{pattern_type.value}:")
                    for p in pattern_list[:3]:  # Show top 3
                        print(f"  - {p.name} at {p.price_level:.2f} (strength: {p.strength:.2f})")
    
    asyncio.run(test())

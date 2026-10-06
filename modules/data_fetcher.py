"""
Data Fetcher Module - Fetches XAUUSD data from BIQUOTE API
Correct endpoints:
  Price  -> https://biquote.io/api/XAUUSD
  OHLC   -> https://biquote.io/api/XAUUSD/ohlc?interval=1m&limit=200
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from config.settings import config

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str = "1m"

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def body_ratio(self) -> float:
        if self.range == 0:
            return 0.0
        return self.body / self.range

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "timeframe": self.timeframe,
            "is_bullish": self.is_bullish,
            "body": round(self.body, 5),
            "range": round(self.range, 5)
        }

    @classmethod
    def from_biquote_bar(cls, bar: Dict[str, Any], timeframe: str = "1m") -> "Candle":
        ts_raw = bar.get("openTime") or bar.get("timestamp") or bar.get("time")
        if isinstance(ts_raw, (int, float)):
            timestamp = datetime.utcfromtimestamp(ts_raw / 1000 if ts_raw > 1e12 else ts_raw)
        else:
            try:
                timestamp = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00").replace("+00:00", ""))
            except Exception:
                timestamp = datetime.utcnow()
        return cls(
            timestamp=timestamp,
            open=float(bar.get("open", 0)),
            high=float(bar.get("high", 0)),
            low=float(bar.get("low", 0)),
            close=float(bar.get("close", 0)),
            volume=float(bar.get("volume", bar.get("tickVolume", 0))),
            timeframe=timeframe
        )


@dataclass
class MarketData:
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    volume: float = 0.0
    mid: float = 0.0
    spread: float = 0.0
    high: float = 0.0
    low: float = 0.0
    day_diff_percent: float = 0.0
    market_state: str = "open"

    def __post_init__(self):
        if self.mid == 0.0 and self.bid and self.ask:
            self.mid = (self.bid + self.ask) / 2
        if self.spread == 0.0 and self.bid and self.ask:
            self.spread = self.ask - self.bid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bid": round(self.bid, 5),
            "ask": round(self.ask, 5),
            "mid": round(self.mid, 5),
            "spread": round(self.spread, 5),
            "high": round(self.high, 5),
            "low": round(self.low, 5),
            "day_diff_percent": round(self.day_diff_percent, 4),
            "market_state": self.market_state,
            "timestamp": self.timestamp.isoformat(),
            "volume": self.volume
        }


class BIQuoteClient:
    """Client for biquote.io – correct endpoints"""

    def __init__(self):
        self.base_url = "https://biquote.io"
        self.symbol = getattr(config.biquote, "SYMBOL", "XAUUSD") or "XAUUSD"
        self.timeout = getattr(config.biquote, "TIMEOUT", 30)
        self.max_retries = getattr(config.biquote, "MAX_RETRIES", 3)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_err = None
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 429:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    text = await resp.text()
                    last_err = f"HTTP {resp.status}: {text[:200]}"
                    logger.warning(f"{path} -> {last_err}")
                    await asyncio.sleep(0.6 * (attempt + 1))
            except Exception as e:
                last_err = str(e)
                logger.warning(f"{path} attempt {attempt+1}: {e}")
                await asyncio.sleep(0.8 * (attempt + 1))
        raise Exception(f"Failed after {self.max_retries} attempts: {url} | {last_err}")

    async def get_current_price(self) -> MarketData:
        """GET /api/XAUUSD"""
        data = await self._get(f"/api/{self.symbol}")
        ts_raw = data.get("timestamp") or data.get("lastQuoteAt") or data.get("time")
        try:
            timestamp = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00").replace("+00:00", ""))
        except Exception:
            timestamp = datetime.utcnow()

        bid = float(data.get("bid", 0))
        ask = float(data.get("ask", 0))
        mid = float(data.get("mid", (bid + ask) / 2 if bid and ask else 0))

        return MarketData(
            symbol=data.get("symbol", self.symbol),
            bid=bid,
            ask=ask,
            mid=mid,
            spread=float(data.get("spread", ask - bid if ask and bid else 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            day_diff_percent=float(data.get("dayDiffPercent", 0)),
            market_state=data.get("marketState", "open"),
            timestamp=timestamp,
            volume=float(data.get("volume", 0))
        )

    async def get_historical_candles(self, timeframe: str = "1m", limit: int = 200) -> List[Candle]:
        """GET /api/XAUUSD/ohlc?interval=1m&limit=200"""
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "4h": "4h", "1d": "1d"
        }
        interval = interval_map.get(timeframe, "1m")

        data = await self._get(
            f"/api/{self.symbol}/ohlc",
            params={"interval": interval, "limit": limit}
        )
        bars = data.get("bars", [])
        candles = []
        for bar in bars:
            try:
                candles.append(Candle.from_biquote_bar(bar, timeframe))
            except Exception as e:
                logger.debug(f"Skip bar: {e}")
                continue
        candles.sort(key=lambda c: c.timestamp)
        return candles

    async def get_multiple_timeframes(self, timeframes: List[str] = None) -> Dict[str, List[Candle]]:
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "30m", "1h"]
        results = {}
        tasks = [self.get_historical_candles(tf, 200) for tf in timeframes]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        for tf, res in zip(timeframes, fetched):
            results[tf] = res if isinstance(res, list) else []
        return results


class DataCache:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._ts: Dict[str, datetime] = {}
        self._ttl = timedelta(seconds=getattr(config.app, "CACHE_TTL", 30))
        self._lock = asyncio.Lock()

    async def get_price(self, client: BIQuoteClient) -> MarketData:
        key = "price"
        async with self._lock:
            if key in self._cache and datetime.utcnow() - self._ts.get(key, datetime.min) < self._ttl:
                return self._cache[key]
            price = await client.get_current_price()
            self._cache[key] = price
            self._ts[key] = datetime.utcnow()
            return price

    async def get_candles(self, client: BIQuoteClient, tf: str, limit: int = 200) -> List[Candle]:
        key = f"c_{tf}_{limit}"
        async with self._lock:
            if key in self._cache and datetime.utcnow() - self._ts.get(key, datetime.min) < self._ttl:
                return self._cache[key]
            candles = await client.get_historical_candles(tf, limit)
            self._cache[key] = candles
            self._ts[key] = datetime.utcnow()
            return candles

    def clear(self):
        self._cache.clear()
        self._ts.clear()


data_cache = DataCache()

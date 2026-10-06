"""
Data Fetcher Module - Fetches XAUUSD data from BIQUOTE API
Optimized for speed and reliability
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
    def from_dict(cls, data: Dict[str, Any], timeframe: str = "1m") -> "Candle":
        ts = data.get("timestamp") or data.get("time") or data.get("t")
        if isinstance(ts, (int, float)):
            timestamp = datetime.utcfromtimestamp(ts / 1000 if ts > 1e12 else ts)
        else:
            try:
                timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace("+00:00", ""))
            except Exception:
                timestamp = datetime.utcnow()
        return cls(
            timestamp=timestamp,
            open=float(data.get("open", data.get("o", 0))),
            high=float(data.get("high", data.get("h", 0))),
            low=float(data.get("low", data.get("l", 0))),
            close=float(data.get("close", data.get("c", 0))),
            volume=float(data.get("volume", data.get("v", 0))),
            timeframe=timeframe
        )


@dataclass
class MarketData:
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    volume: float = 0.0

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "mid": round(self.mid, 5),
            "spread": round(self.spread, 5),
            "timestamp": self.timestamp.isoformat(),
            "volume": self.volume
        }


class BIQuoteClient:
    def __init__(self):
        self.base_url = config.biquote.BASE_URL
        self.symbol = config.biquote.SYMBOL
        self.timeout = config.biquote.TIMEOUT
        self.max_retries = config.biquote.MAX_RETRIES
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "error" not in data:
                            return data
                        logger.warning(f"API returned error: {data}")
                    elif response.status == 429:
                        await asyncio.sleep(1.5 * (attempt + 1))
                    else:
                        logger.error(f"HTTP {response.status} for {url}")
                        await asyncio.sleep(0.8 * (attempt + 1))
            except asyncio.TimeoutError:
                logger.warning(f"Timeout attempt {attempt+1} for {url}")
                await asyncio.sleep(1.0 * (attempt + 1))
            except Exception as e:
                logger.error(f"Request error attempt {attempt+1}: {e}")
                await asyncio.sleep(1.0 * (attempt + 1))
        raise Exception(f"Failed after {self.max_retries} attempts: {url}")

    async def get_current_price(self) -> MarketData:
        try:
            data = await self._make_request("ticker", {"symbol": self.symbol})
            if data and "data" in data and data["data"]:
                t = data["data"][0]
                return MarketData(
                    symbol=self.symbol,
                    bid=float(t.get("bid", t.get("b", 0))),
                    ask=float(t.get("ask", t.get("a", 0))),
                    timestamp=datetime.utcnow(),
                    volume=float(t.get("volume", t.get("v", 0)))
                )
            if "bid" in data:
                return MarketData(
                    symbol=self.symbol,
                    bid=float(data["bid"]),
                    ask=float(data.get("ask", data["bid"])),
                    timestamp=datetime.utcnow(),
                    volume=float(data.get("volume", 0))
                )
            raise ValueError(f"Unexpected ticker format: {list(data.keys())}")
        except Exception as e:
            logger.error(f"get_current_price failed: {e}")
            raise

    async def get_historical_candles(self, timeframe: str = "1m", limit: int = 300) -> List[Candle]:
        try:
            data = await self._make_request("klines", {
                "symbol": self.symbol,
                "interval": timeframe,
                "limit": limit
            })
            candles = []
            raw = data.get("data", data if isinstance(data, list) else [])
            for item in raw:
                try:
                    candles.append(Candle.from_dict(item, timeframe))
                except Exception:
                    continue
            candles.sort(key=lambda c: c.timestamp)
            return candles
        except Exception as e:
            logger.error(f"get_historical_candles({timeframe}) failed: {e}")
            return []

    async def get_multiple_timeframes(self, timeframes: List[str] = None) -> Dict[str, List[Candle]]:
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "30m", "1h"]
        results = {}
        tasks = [self.get_historical_candles(tf, 250) for tf in timeframes]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        for tf, res in zip(timeframes, fetched):
            results[tf] = res if isinstance(res, list) else []
        return results


class DataCache:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._ts: Dict[str, datetime] = {}
        self._ttl = timedelta(seconds=config.app.CACHE_TTL)
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

    async def get_candles(self, client: BIQuoteClient, tf: str, limit: int = 250) -> List[Candle]:
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

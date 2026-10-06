"""
Data Fetcher Module - Fetches XAUUSD data from BIQUOTE API
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from config.settings import config

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Represents a single candlestick"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "timeframe": self.timeframe
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], timeframe: str = "1m") -> 'Candle':
        return cls(
            timestamp=datetime.fromisoformat(data.get("timestamp", data.get("time", ""))),
            open=float(data.get("open", data.get("o", 0))),
            high=float(data.get("high", data.get("h", 0))),
            low=float(data.get("low", data.get("l", 0))),
            close=float(data.get("close", data.get("c", 0))),
            volume=float(data.get("volume", data.get("v", 0))),
            timeframe=timeframe
        )


@dataclass
class MarketData:
    """Represents current market data"""
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    volume: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "timestamp": self.timestamp.isoformat(),
            "volume": self.volume
        }


class BIQuoteClient:
    """Client for fetching data from BIQUOTE API"""
    
    def __init__(self):
        self.base_url = config.biquote.BASE_URL
        self.symbol = config.biquote.SYMBOL
        self.timeout = config.biquote.TIMEOUT
        self.max_retries = config.biquote.MAX_RETRIES
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "error" not in data:
                            return data
                        else:
                            logger.error(f"API Error: {data.get('error', 'Unknown error')}")
                    elif response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 1))
                        await asyncio.sleep(retry_after * (attempt + 1))
                    else:
                        logger.error(f"HTTP Error: {response.status}")
                        await asyncio.sleep(1 * (attempt + 1))
                        
            except aiohttp.ClientError as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                await asyncio.sleep(1 * (attempt + 1))
        
        raise Exception(f"Failed to fetch data from {url} after {self.max_retries} attempts")
    
    async def get_current_price(self) -> MarketData:
        """Get current bid/ask price"""
        try:
            data = await self._make_request("ticker", {"symbol": self.symbol})
            
            if data and "data" in data and len(data["data"]) > 0:
                ticker = data["data"][0]
                return MarketData(
                    symbol=self.symbol,
                    bid=float(ticker.get("bid", ticker.get("b", 0))),
                    ask=float(ticker.get("ask", ticker.get("a", 0))),
                    timestamp=datetime.fromisoformat(ticker.get("timestamp", datetime.utcnow().isoformat())),
                    volume=float(ticker.get("volume", 0))
                )
            else:
                logger.error(f"Unexpected response format: {data}")
                raise ValueError("Invalid ticker data format")
                
        except Exception as e:
            logger.error(f"Failed to get current price: {e}")
            raise
    
    async def get_historical_candles(
        self, 
        timeframe: str = "1m", 
        limit: int = 1000
    ) -> List[Candle]:
        """Get historical candlestick data"""
        try:
            # Convert timeframe to minutes
            tf_map = {
                "1m": 1,
                "5m": 5,
                "15m": 15,
                "30m": 30,
                "1h": 60,
                "4h": 240,
                "1d": 1440
            }
            tf_minutes = tf_map.get(timeframe, 1)
            
            data = await self._make_request(
                "klines", 
                {
                    "symbol": self.symbol,
                    "interval": timeframe,
                    "limit": limit
                }
            )
            
            candles = []
            if data and "data" in data:
                for candle_data in data["data"]:
                    candle = Candle.from_dict(candle_data, timeframe)
                    candles.append(candle)
            
            return candles
            
        except Exception as e:
            logger.error(f"Failed to get historical candles: {e}")
            raise
    
    async def get_multiple_timeframes(
        self, 
        timeframes: List[str] = None
    ) -> Dict[str, List[Candle]]:
        """Get candles for multiple timeframes"""
        if timeframes is None:
            timeframes = [f"{tf}m" for tf in config.technical.TIMEFRAMES]
        
        results = {}
        tasks = []
        
        for tf in timeframes:
            task = asyncio.create_task(
                self.get_historical_candles(timeframe=tf, limit=500)
            )
            tasks.append((tf, task))
        
        for tf, task in tasks:
            try:
                results[tf] = await task
            except Exception as e:
                logger.error(f"Failed to fetch {tf}: {e}")
                results[tf] = []
        
        return results
    
    async def get_order_book(self, depth: int = 50) -> Dict[str, Any]:
        """Get order book data"""
        try:
            data = await self._make_request(
                "depth",
                {"symbol": self.symbol, "limit": depth}
            )
            return data
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            raise
    
    async def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades"""
        try:
            data = await self._make_request(
                "trades",
                {"symbol": self.symbol, "limit": limit}
            )
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            raise


class DataCache:
    """Cache for market data to reduce API calls"""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.last_fetch: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(seconds=config.app.CACHE_TTL)
        self.lock = asyncio.Lock()
    
    async def get_cached_candles(
        self, 
        timeframe: str, 
        limit: int,
        fetcher: BIQuoteClient
    ) -> List[Candle]:
        """Get candles from cache or fetch fresh"""
        cache_key = f"candles_{timeframe}_{limit}"
        
        async with self.lock:
            if cache_key in self.cache:
                last_fetch = self.last_fetch.get(cache_key, datetime.min)
                if datetime.utcnow() - last_fetch < self.cache_ttl:
                    return self.cache[cache_key]
            
            # Fetch fresh data
            candles = await fetcher.get_historical_candles(timeframe, limit)
            self.cache[cache_key] = candles
            self.last_fetch[cache_key] = datetime.utcnow()
            return candles
    
    async def get_cached_price(self, fetcher: BIQuoteClient) -> MarketData:
        """Get current price from cache or fetch fresh"""
        cache_key = "current_price"
        
        async with self.lock:
            if cache_key in self.cache:
                last_fetch = self.last_fetch.get(cache_key, datetime.min)
                if datetime.utcnow() - last_fetch < self.cache_ttl:
                    return self.cache[cache_key]
            
            # Fetch fresh data
            price = await fetcher.get_current_price()
            self.cache[cache_key] = price
            self.last_fetch[cache_key] = datetime.utcnow()
            return price
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.last_fetch.clear()


# Global instances
biquote_client = BIQuoteClient()
data_cache = DataCache()


async def test_connection():
    """Test API connection"""
    try:
        async with BIQuoteClient() as client:
            price = await client.get_current_price()
            print(f"✓ BIQUOTE API Connection OK")
            print(f"  Current {price.symbol} Price: Bid={price.bid}, Ask={price.ask}")
            return True
    except Exception as e:
        print(f"✗ BIQUOTE API Connection Failed: {e}")
        return False


if __name__ == "__main__":
    async def main():
        await test_connection()
    
    asyncio.run(main())

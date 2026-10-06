"""
Configuration Settings for VIP.BOT - Professional XAUUSD Trading Bot
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BIQuoteConfig:
    """BIQUOTE API Configuration"""
    BASE_URL: str = "https://biquote.io/api"
    SYMBOL: str = "XAUUSD"
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    

@dataclass
class TelegramConfig:
    """Telegram Bot Configuration"""
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    ADMIN_ID: str = os.getenv("TELEGRAM_ADMIN_ID", "")
    MESSAGE_FORMAT: str = "HTML"
    

@dataclass
class TradingConfig:
    """Trading Strategy Configuration"""
    DAILY_TRADES_LIMIT: int = 20
    LOT_SIZE: float = 0.1
    LEVERAGE: int = 100
    
    # Stop Loss and Take Profit (in points)
    DEFAULT_STOP_LOSS: int = 50
    DEFAULT_TAKE_PROFIT: int = 100
    TRAILING_STOP: bool = True
    TRAILING_STOP_DISTANCE: int = 30
    
    # Scalping Settings
    SCALPING_AGGRESSION: float = 0.8  # 0.1-1.0
    MIN_PROFIT_TARGET: int = 10
    MAX_DRAWDOWN_PER_TRADE: float = 0.02  # 2%
    

@dataclass
class TechnicalAnalysisConfig:
    """Technical Analysis Configuration"""
    # Timeframes (in minutes)
    TIMEFRAMES: List[int] = field(default_factory=lambda: [1, 5, 15, 30, 60, 240])
    
    # Candlestick Patterns
    ENABLE_CANDLE_PATTERNS: bool = True
    CANDLE_PATTERN_LOOKBACK: int = 100
    
    # Support and Resistance
    ENABLE_SR_LEVELS: bool = True
    SR_LOOKBACK_PERIODS: int = 500
    SR_STRENGTH_THRESHOLD: float = 0.6
    
    # Trend Detection
    ENABLE_TREND_ANALYSIS: bool = True
    TREND_PERIOD: int = 50
    
    # Volume Analysis
    ENABLE_VOLUME_ANALYSIS: bool = True
    VOLUME_SPIKE_THRESHOLD: float = 2.0
    

@dataclass
class RiskManagementConfig:
    """Risk Management Configuration"""
    MAX_DAILY_LOSS: float = 0.10  # 10% of capital
    MAX_DAILY_PROFIT: float = 0.20  # 20% of capital
    MAX_OPEN_TRADES: int = 5
    MAX_TRADE_RISK_PERCENT: float = 0.02  # 2% per trade
    
    # Drawdown Protection
    MAX_DRAWDOWN: float = 0.15  # 15%
    STOP_TRADING_AT_DRAWDOWN: float = 0.12  # 12%
    

@dataclass
class SignalConfig:
    """Signal Generation Configuration"""
    SIGNAL_CONFIDENCE_THRESHOLD: float = 0.7
    MIN_SIGNAL_STRENGTH: float = 0.65
    CONFIRMATION_REQUIRED: bool = True
    CONFIRMATION_TIMEFRAMES: int = 2
    
    # Signal Types
    ENABLE_BUY_SIGNALS: bool = True
    ENABLE_SELL_SIGNALS: bool = True
    ENABLE_REVERSAL_SIGNALS: bool = True
    ENABLE_BREAKOUT_SIGNALS: bool = True
    

@dataclass
class AppConfig:
    """Main Application Configuration"""
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = "INFO"
    DATA_STORE_DAYS: int = 30
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 60  # seconds
    

# Global Configuration Instance
class Config:
    """Global Configuration Manager"""
    
    def __init__(self):
        self.biquote = BIQuoteConfig()
        self.telegram = TelegramConfig()
        self.trading = TradingConfig()
        self.technical = TechnicalAnalysisConfig()
        self.risk = RiskManagementConfig()
        self.signal = SignalConfig()
        self.app = AppConfig()
    
    def load_from_env(self):
        """Load configuration from environment variables"""
        # BIQUOTE
        if "BIQUOTE_BASE_URL" in os.environ:
            self.biquote.BASE_URL = os.environ["BIQUOTE_BASE_URL"]
        if "BIQUOTE_SYMBOL" in os.environ:
            self.biquote.SYMBOL = os.environ["BIQUOTE_SYMBOL"]
        
        # Telegram
        if "TELEGRAM_BOT_TOKEN" in os.environ:
            self.telegram.BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
        if "TELEGRAM_CHANNEL_ID" in os.environ:
            self.telegram.CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
        if "TELEGRAM_ADMIN_ID" in os.environ:
            self.telegram.ADMIN_ID = os.environ["TELEGRAM_ADMIN_ID"]
        
        # Trading
        if "DAILY_TRADES_LIMIT" in os.environ:
            self.trading.DAILY_TRADES_LIMIT = int(os.environ["DAILY_TRADES_LIMIT"])
        if "LOT_SIZE" in os.environ:
            self.trading.LOT_SIZE = float(os.environ["LOT_SIZE"])
        
        # Debug
        if "DEBUG" in os.environ:
            self.app.DEBUG = os.environ["DEBUG"].lower() == "true"


# Create global config instance
config = Config()
config.load_from_env()


if __name__ == "__main__":
    print("VIP.BOT Configuration:")
    print(f"  BIQUOTE: {config.biquote.BASE_URL}/{config.biquote.SYMBOL}")
    print(f"  Daily Trades Limit: {config.trading.DAILY_TRADES_LIMIT}")
    print(f"  Debug Mode: {config.app.DEBUG}")

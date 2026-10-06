"""
VIP.BOT Configuration Settings
Professional XAUUSD Trading Bot - Glass Dashboard Edition
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


# ============================================================
#  🔑 ضع توكن التليجرام والآي دي هنا مباشرة (بدون متغيرات بيئة)
# ============================================================
TELEGRAM_BOT_TOKEN = "8976865494:AAEoEOA17SLSQf1V8SrFvYE31NgPZOGuEs0"
TELEGRAM_CHANNEL_ID = "@PQYNC"
TELEGRAM_ADMIN_ID = "8952278702"
# ============================================================


@dataclass
class BIQuoteConfig:
    BASE_URL: str = "https://biquote.io/api"
    SYMBOL: str = "XAUUSD"
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3


@dataclass
class TelegramConfig:
    BOT_TOKEN: str = TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHANNEL_ID: str = TELEGRAM_CHANNEL_ID or os.getenv("TELEGRAM_CHANNEL_ID", "")
    ADMIN_ID: str = TELEGRAM_ADMIN_ID or os.getenv("TELEGRAM_ADMIN_ID", "")
    MESSAGE_FORMAT: str = "HTML"


@dataclass
class TradingConfig:
    DAILY_TRADES_LIMIT: int = 25
    LOT_SIZE: float = 0.1
    LEVERAGE: int = 100
    DEFAULT_STOP_LOSS: int = 40
    DEFAULT_TAKE_PROFIT: int = 80
    TRAILING_STOP: bool = True
    TRAILING_STOP_DISTANCE: int = 25
    SCALPING_AGGRESSION: float = 0.75
    MIN_PROFIT_TARGET: int = 8
    MAX_DRAWDOWN_PER_TRADE: float = 0.02
    MIN_SIGNAL_STRENGTH: float = 0.48
    MIN_CONFIDENCE: float = 0.50


@dataclass
class TechnicalAnalysisConfig:
    TIMEFRAMES: List[int] = field(default_factory=lambda: [1, 5, 15, 30, 60, 240])
    ENABLE_CANDLE_PATTERNS: bool = True
    CANDLE_PATTERN_LOOKBACK: int = 120
    ENABLE_SR_LEVELS: bool = True
    SR_LOOKBACK_PERIODS: int = 400
    SR_STRENGTH_THRESHOLD: float = 0.55
    ENABLE_TREND_ANALYSIS: bool = True
    TREND_PERIOD: int = 40
    ENABLE_VOLUME_ANALYSIS: bool = True
    VOLUME_SPIKE_THRESHOLD: float = 1.7


@dataclass
class RiskManagementConfig:
    MAX_DAILY_LOSS: float = 0.12
    MAX_DAILY_PROFIT: float = 0.25
    MAX_OPEN_TRADES: int = 6
    MAX_TRADE_RISK_PERCENT: float = 0.02
    MAX_DRAWDOWN: float = 0.18
    STOP_TRADING_AT_DRAWDOWN: float = 0.14


@dataclass
class SignalConfig:
    SIGNAL_CONFIDENCE_THRESHOLD: float = 0.50
    MIN_SIGNAL_STRENGTH: float = 0.48
    CONFIRMATION_REQUIRED: bool = False
    CONFIRMATION_TIMEFRAMES: int = 1
    ENABLE_BUY_SIGNALS: bool = True
    ENABLE_SELL_SIGNALS: bool = True
    ENABLE_REVERSAL_SIGNALS: bool = True
    ENABLE_BREAKOUT_SIGNALS: bool = True
    CANDLE_PATTERN_WEIGHT: float = 0.45
    INDICATOR_WEIGHT: float = 0.30
    VOLUME_WEIGHT: float = 0.15
    TREND_WEIGHT: float = 0.10


@dataclass
class WebConfig:
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", 10000))
    DEBUG: bool = False
    REFRESH_INTERVAL_MS: int = 1000


@dataclass
class AppConfig:
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = "INFO"
    DATA_STORE_DAYS: int = 30
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 2              # cache price/candles for 2 seconds only
    BOT_LOOP_INTERVAL: float = 5.0  # analysis cycle every 5 seconds (faster)


class Config:
    def __init__(self):
        self.biquote = BIQuoteConfig()
        self.telegram = TelegramConfig()
        self.trading = TradingConfig()
        self.technical = TechnicalAnalysisConfig()
        self.risk = RiskManagementConfig()
        self.signal = SignalConfig()
        self.web = WebConfig()
        self.app = AppConfig()

    def load_from_env(self):
        if "BIQUOTE_BASE_URL" in os.environ:
            self.biquote.BASE_URL = os.environ["BIQUOTE_BASE_URL"]
        if "BIQUOTE_SYMBOL" in os.environ:
            self.biquote.SYMBOL = os.environ["BIQUOTE_SYMBOL"]
        if "DAILY_TRADES_LIMIT" in os.environ:
            self.trading.DAILY_TRADES_LIMIT = int(os.environ["DAILY_TRADES_LIMIT"])
        if "LOT_SIZE" in os.environ:
            self.trading.LOT_SIZE = float(os.environ["LOT_SIZE"])
        if "DEBUG" in os.environ:
            self.app.DEBUG = os.environ["DEBUG"].lower() == "true"
        if "PORT" in os.environ:
            self.web.PORT = int(os.environ["PORT"])


config = Config()
config.load_from_env()

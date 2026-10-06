# VIP.BOT - Professional XAUUSD Trading Bot

## 📊 Overview

VIP.BOT is a professional, aggressive scalping trading bot for XAUUSD (Gold vs US Dollar) that executes **20 trades per day** with comprehensive technical analysis, pattern detection, and risk management.

## ✨ Features

### 🎯 Core Capabilities
- **20 Trades Per Day** - Aggressive scalping strategy
- **Multi-Timeframe Analysis** - 1m, 5m, 15m, 30m, 1h, 4h
- **50+ Technical Indicators** - RSI, MACD, Bollinger Bands, Stochastic, ATR, Moving Averages
- **Advanced Pattern Detection** - Peaks, Valleys, Breakouts, Reversals
- **Comprehensive Risk Management** - Drawdown protection, position sizing, daily limits
- **Telegram Integration** - Real-time signals and notifications

### 📈 Technical Analysis
- **Candlestick Pattern Recognition** - Hammer, Shooting Star, Engulfing, Doji, etc.
- **Support & Resistance Detection** - Automatic level identification
- **Trend Analysis** - Short, Medium, Long-term trend detection
- **Volume Analysis** - Spike detection and confirmation
- **Breakout Detection** - Support/Resistance breakouts
- **Reversal Detection** - Early trend reversal identification

### ⚡ Scalping Strategy
- **Aggressive Entry** - High-probability trade signals
- **Trailing Stop Loss** - Dynamic stop loss management
- **1:3 Risk-Reward Ratio** - Optimal profit targets
- **Volume Confirmation** - Trade with momentum
- **Multi-Timeframe Confirmation** - Higher accuracy signals

### 🛡️ Risk Management
- **2% Max Risk Per Trade** - Controlled position sizing
- **10% Max Daily Loss** - Daily loss limit
- **5 Open Trades Max** - Portfolio diversification
- **15% Max Drawdown** - Account protection
- **Automatic Stop Trading** - When limits are reached

### 📱 Telegram Notifications
- **Real-time Signals** - Entry, Stop Loss, Take Profit
- **Trade Notifications** - Open and close alerts
- **Daily Summary** - Performance reports
- **Risk Alerts** - Critical warnings

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip
- Telegram Bot Token (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/o7sa/VIP.BOT.git
cd VIP.BOT

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file or set environment variables:

```bash
# BIQUOTE API (default values)
BIQUOTE_BASE_URL=https://biquote.io/api
BIQUOTE_SYMBOL=XAUUSD

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=your_channel_id
TELEGRAM_ADMIN_ID=your_admin_id

# Trading Settings (optional)
DAILY_TRADES_LIMIT=20
LOT_SIZE=0.1
LEVERAGE=100

# Debug
DEBUG=true
```

### Run the Bot

```bash
# Test mode (single cycle)
python bot.py --test

# Continuous trading (60 second interval)
python bot.py --continuous --interval 60

# Daily session (until daily limit)
python bot.py --daily

# Debug mode
python bot.py --test --debug
```

## 📁 Project Structure

```
VIP.BOT/
├── bot.py                 # Main bot entry point
├── config/
│   ├── __init__.py
│   └── settings.py        # Configuration settings
├── modules/
│   ├── __init__.py
│   ├── data_fetcher.py    # BIQUOTE API client
│   ├── technical_analyzer.py  # Technical analysis engine
│   └── pattern_detector.py  # Chart pattern detection
├── strategies/
│   ├── __init__.py
│   └── scalping_strategy.py  # Aggressive scalping strategy
├── utils/
│   ├── __init__.py
│   └── risk_manager.py    # Risk management system
├── signals/
│   ├── __init__.py
│   └── telegram_sender.py # Telegram notifications
├── data/                 # Cached market data
├── logs/                 # Log files
└── README.md
```

## 🔧 Configuration Options

### Trading Settings (`config/settings.py`)

```python
# Daily trading limits
DAILY_TRADES_LIMIT = 20
LOT_SIZE = 0.1
LEVERAGE = 100

# Stop Loss and Take Profit
DEFAULT_STOP_LOSS = 50      # points
DEFAULT_TAKE_PROFIT = 100    # points
TRAILING_STOP = True
TRAILING_STOP_DISTANCE = 30

# Scalping aggression (0.1-1.0)
SCALPING_AGGRESSION = 0.8
MIN_PROFIT_TARGET = 10
MAX_DRAWDOWN_PER_TRADE = 0.02
```

### Technical Analysis Settings

```python
# Timeframes (in minutes)
TIMEFRAMES = [1, 5, 15, 30, 60, 240]

# Candlestick patterns
ENABLE_CANDLE_PATTERNS = True
CANDLE_PATTERN_LOOKBACK = 100

# Support and Resistance
ENABLE_SR_LEVELS = True
SR_LOOKBACK_PERIODS = 500
SR_STRENGTH_THRESHOLD = 0.6
```

### Risk Management Settings

```python
# Daily limits
MAX_DAILY_LOSS = 0.10    # 10%
MAX_DAILY_PROFIT = 0.20  # 20%
MAX_OPEN_TRADES = 5
MAX_TRADE_RISK_PERCENT = 0.02  # 2%

# Drawdown protection
MAX_DRAWDOWN = 0.15      # 15%
STOP_TRADING_AT_DRAWDOWN = 0.12  # 12%
```

## 📊 Signal Format

### Telegram Message Example

```
⚡ إشَارَة عَدْوَانِيَّة ⚡

🎯 هذا وقت للدخول بقوة!

📊 الاتجاه: شراء عدواني
💰 سعر الدخول: 2000.50
⛔ ستوب لوس: 1995.00
🎯 تيك بروفيت: 2010.00

💪 قوة الإشارة: 90.0% ⭐
🎯 ثقة الإشارة: 85.0% ✅

🔥 سبب الدخول:
Strong bullish momentum with RSI oversold and MACD crossover

📊 المؤشرات:
• RSI: 25.00 (مُشْتَرى إلى حد كبير)
• MACD: 0.5000

🔄 أنماط قوية:
Bullish Engulfing, Hammer

⏰ الوقت: 2024-01-01 12:00:00 UTC

⚠️ تحذير: هذه إشارة عدوانية مع مخاطرة عالية، ولكن مع احتمال ربح كبير
```

## 🎯 Strategy Logic

### Signal Generation
1. **Technical Analysis** - Analyze 50+ indicators across multiple timeframes
2. **Pattern Detection** - Identify peaks, valleys, breakouts, reversals
3. **Volume Confirmation** - Check for volume spikes and confirmation
4. **Trend Confirmation** - Verify trend alignment across timeframes
5. **Signal Scoring** - Calculate overall signal strength (0-100%)

### Trade Execution
1. **Signal Threshold** - Only execute trades with strength > 60%
2. **Risk Check** - Verify trade doesn't exceed risk limits
3. **Position Sizing** - Calculate lot size based on risk percentage
4. **Stop Loss/Take Profit** - Set based on ATR and volatility

### Trade Management
1. **Trailing Stop** - Adjust stop loss as trade moves in favor
2. **Exit Conditions** - Stop loss, take profit, or manual close
3. **Performance Tracking** - Monitor P&L and statistics

## 📈 Performance Metrics

The bot tracks and reports:
- **Win Rate** - Percentage of winning trades
- **Profit Factor** - Total profit / total loss
- **Max Drawdown** - Maximum account drawdown
- **Daily P&L** - Daily profit/loss
- **Account Growth** - Overall performance

## 🛠️ Development

### Adding New Indicators
```python
# In technical_analyzer.py
def _calculate_new_indicator(self, prices: List[float], period: int) -> List[float]:
    # Your indicator calculation
    return indicator_values
```

### Adding New Patterns
```python
# In pattern_detector.py
def _detect_new_pattern(self, candles: List[Candle]) -> List[Pattern]:
    # Your pattern detection logic
    return patterns
```

### Custom Strategies
```python
# Create new strategy in strategies/
class MyStrategy:
    def analyze(self, candles: List[Candle]) -> AnalysisResult:
        # Your strategy logic
        pass
```

## 📝 License

This project is proprietary. All rights reserved.

## 🤝 Support

For support and questions, please contact the development team.

## 🎓 Trading Disclaimer

**IMPORTANT**: Trading involves substantial risk. This bot is for educational purposes only. 
Do not use with real money without thorough testing and understanding of the risks.

- Past performance is not indicative of future results
- You may lose all your invested capital
- Trade at your own risk
- This is not financial advice

---

**VIP.BOT** - Professional XAUUSD Trading Bot | Version 1.0.0 | © 2024

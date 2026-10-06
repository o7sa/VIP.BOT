"""
VIP.BOT - Professional XAUUSD Trading Bot
Aggressive Scalping Strategy with 20 Trades Per Day

Features:
- Technical Analysis with 50+ indicators
- Advanced Pattern Detection (Peaks, Valleys, Breakouts)
- Aggressive Scalping Strategy
- Comprehensive Risk Management
- Telegram Signal Notifications
- Multi-Timeframe Analysis
- Support and Resistance Detection
- Volume Analysis
- Trend Detection
- Candle Pattern Recognition
"""

import asyncio
import logging
import sys
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Any
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import modules
from config.settings import config, BIQuoteConfig
from modules.data_fetcher import BIQuoteClient, MarketData, data_cache
from modules.technical_analyzer import TechnicalAnalyzer, technical_analyzer
from modules.pattern_detector import PatternDetector, pattern_detector
from strategies.scalping_strategy import ScalpingStrategy, scalping_strategy
from utils.risk_manager import RiskManager, risk_manager
from signals.telegram_sender import TelegramSender, telegram_sender


class VIPBot:
    """Main Trading Bot Class"""
    
    def __init__(self):
        self.name = "VIP.BOT"
        self.version = "1.0.0"
        self.start_time = datetime.utcnow()
        self.is_running = False
        self.trade_count = 0
        self.signal_count = 0
        
        # Initialize components
        self.client = BIQuoteClient()
        self.analyzer = technical_analyzer
        self.detector = pattern_detector
        self.strategy = scalping_strategy
        self.risk_manager = risk_manager
        self.telegram = telegram_sender
        
        # State
        self.last_trade_time = None
        self.last_signal_time = None
        self.daily_stats = {
            "trades": 0,
            "signals": 0,
            "profit": 0.0,
            "loss": 0.0
        }
    
    async def initialize(self):
        """Initialize the bot"""
        logger.info(f"Initializing {self.name} v{self.version}")
        logger.info(f"Configuration: {config.biquote.BASE_URL}/{config.biquote.SYMBOL}")
        logger.info(f"Daily trade limit: {config.trading.DAILY_TRADES_LIMIT}")
        logger.info(f"Debug mode: {config.app.DEBUG}")
        
        # Test connections
        await self._test_connections()
        
        logger.info("Bot initialized successfully")
    
    async def _test_connections(self):
        """Test all external connections"""
        logger.info("Testing connections...")
        
        # Test BIQUOTE API
        try:
            async with BIQuoteClient() as client:
                price = await client.get_current_price()
                logger.info(f"✓ BIQUOTE API: {price.symbol} = {price.bid}/{price.ask}")
        except Exception as e:
            logger.error(f"✗ BIQUOTE API: {e}")
            raise
        
        # Test Telegram (if configured)
        if config.telegram.BOT_TOKEN and config.telegram.CHANNEL_ID:
            try:
                async with TelegramSender() as sender:
                    test_msg = "✅ اختبار اتصال - VIP.BOT جاهز للعمل"
                    result = await sender.send_message(test_msg)
                    if result and result.get("ok"):
                        logger.info("✓ Telegram: Connected")
                    else:
                        logger.warning("⚠ Telegram: Connection failed")
            except Exception as e:
                logger.warning(f"⚠ Telegram: {e}")
        else:
            logger.info("⚠ Telegram: Not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID)")
    
    async def fetch_market_data(self) -> Dict[str, Any]:
        """Fetch current market data"""
        data = {}
        
        try:
            async with self.client as client:
                # Get current price
                price = await client.get_current_price()
                data["price"] = price
                
                # Get historical candles for multiple timeframes
                timeframes = ["1m", "5m", "15m", "30m", "1h"]
                candles_dict = await client.get_multiple_timeframes(timeframes)
                data["candles"] = candles_dict
                
                logger.debug(f"Fetched data: price={price.bid}, timeframes={list(candles_dict.keys())}")
                
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            raise
        
        return data
    
    async def analyze_market(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive market analysis"""
        analysis = {}
        
        try:
            price = data.get("price")
            candles_dict = data.get("candles", {})
            
            # Analyze each timeframe
            timeframe_analyses = {}
            for timeframe, candles in candles_dict.items():
                if candles:
                    try:
                        result = self.analyzer.analyze(candles, timeframe)
                        timeframe_analyses[timeframe] = result
                    except Exception as e:
                        logger.error(f"Failed to analyze {timeframe}: {e}")
            
            analysis["timeframes"] = timeframe_analyses
            analysis["current_price"] = price.bid if price else None
            
            # Detect patterns
            for timeframe, candles in candles_dict.items():
                if candles:
                    patterns = self.detector.detect_all_patterns(candles)
                    analysis[f"patterns_{timeframe}"] = patterns
            
            logger.debug(f"Analysis complete: {len(timeframe_analyses)} timeframes")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
        
        return analysis
    
    async def generate_signal(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate trading signal based on analysis"""
        try:
            # Use 1m timeframe for scalping
            tf_1m = analysis.get("timeframes", {}).get("1m")
            if not tf_1m:
                logger.warning("No 1m analysis available")
                return None
            
            # Get patterns for 1m
            patterns_1m = analysis.get("patterns_1m", {})
            
            # Get current price
            current_price = analysis.get("current_price")
            if not current_price:
                logger.warning("No current price available")
                return None
            
            # Generate signal using strategy
            signal = self.strategy._generate_signal(
                tf_1m, 
                patterns_1m, 
                current_price
            )
            
            if signal:
                self.signal_count += 1
                self.daily_stats["signals"] += 1
                self.last_signal_time = datetime.utcnow()
                
                logger.info(f"Generated signal: {signal.direction.value} at {signal.entry_price}")
                
                return signal.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate signal: {e}")
            return None
    
    async def execute_trade(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a trade based on signal"""
        try:
            # Convert signal dict to TradeSignal object
            from strategies.scalping_strategy import TradeSignal, TradeDirection
            
            trade_signal = TradeSignal(
                signal_id=signal.get("signal_id", ""),
                timestamp=datetime.fromisoformat(signal.get("timestamp", "")),
                direction=TradeDirection(signal.get("direction", "BUY")),
                entry_price=signal.get("entry_price", 0),
                stop_loss=signal.get("stop_loss", 0),
                take_profit=signal.get("take_profit", 0),
                confidence=signal.get("confidence", 0),
                strength=signal.get("strength", 0),
                reason=signal.get("reason", ""),
                indicators=signal.get("indicators", {}),
                patterns=signal.get("patterns", []),
                timeframe=signal.get("timeframe", "1m"),
                risk_percent=signal.get("risk_percent", 0.02),
                lot_size=signal.get("lot_size", 0.1)
            )
            
            # Execute trade
            trade = self.strategy._execute_signal(trade_signal)
            
            if trade:
                self.trade_count += 1
                self.daily_stats["trades"] += 1
                self.last_trade_time = datetime.utcnow()
                
                # Update risk manager
                self.risk_manager.record_trade(trade)
                self.risk_manager.update_open_trades(self.strategy.open_trades)
                
                logger.info(f"Executed trade: {trade.trade_id} - {trade.direction.value}")
                
                return trade.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            return None
    
    async def check_trades(self, current_price: float) -> List[Dict[str, Any]]:
        """Check open trades for exit conditions"""
        closed_trades = []
        
        try:
            for trade in self.strategy.open_trades[:]:
                if self.strategy._check_trade_exit(trade, current_price):
                    # Update risk manager
                    self.risk_manager.record_trade(trade)
                    
                    # Update daily stats
                    if trade.profit and trade.profit > 0:
                        self.daily_stats["profit"] += trade.profit
                    elif trade.profit and trade.profit < 0:
                        self.daily_stats["loss"] += abs(trade.profit)
                    
                    closed_trades.append(trade.to_dict())
                else:
                    self.strategy._check_trailing_stop(trade, current_price)
            
            # Update risk manager with current open trades
            self.risk_manager.update_open_trades(self.strategy.open_trades)
            
        except Exception as e:
            logger.error(f"Failed to check trades: {e}")
        
        return closed_trades
    
    async def send_signal_to_telegram(self, signal: Dict[str, Any]) -> bool:
        """Send signal to Telegram"""
        try:
            if not config.telegram.BOT_TOKEN or not config.telegram.CHANNEL_ID:
                logger.debug("Telegram not configured, skipping signal")
                return False
            
            from strategies.scalping_strategy import TradeSignal, TradeDirection
            
            # Convert to TradeSignal object
            trade_signal = TradeSignal(
                signal_id=signal.get("signal_id", ""),
                timestamp=datetime.fromisoformat(signal.get("timestamp", "")),
                direction=TradeDirection(signal.get("direction", "BUY")),
                entry_price=signal.get("entry_price", 0),
                stop_loss=signal.get("stop_loss", 0),
                take_profit=signal.get("take_profit", 0),
                confidence=signal.get("confidence", 0),
                strength=signal.get("strength", 0),
                reason=signal.get("reason", ""),
                indicators=signal.get("indicators", {}),
                patterns=signal.get("patterns", []),
                timeframe=signal.get("timeframe", "1m")
            )
            
            async with TelegramSender() as sender:
                result = await sender.send_signal(trade_signal)
                return result is not None and result.get("ok", False)
                
        except Exception as e:
            logger.error(f"Failed to send signal to Telegram: {e}")
            return False
    
    async def send_trade_to_telegram(self, trade: Dict[str, Any]) -> bool:
        """Send trade notification to Telegram"""
        try:
            if not config.telegram.BOT_TOKEN or not config.telegram.CHANNEL_ID:
                return False
            
            from strategies.scalping_strategy import Trade, TradeDirection, TradeStatus
            
            # Convert to Trade object
            trade_obj = Trade(
                trade_id=trade.get("trade_id", ""),
                signal_id=trade.get("signal_id", ""),
                direction=TradeDirection(trade.get("direction", "BUY")),
                entry_price=trade.get("entry_price", 0),
                entry_time=datetime.fromisoformat(trade.get("entry_time", "")),
                stop_loss=trade.get("stop_loss", 0),
                take_profit=trade.get("take_profit", 0),
                lot_size=trade.get("lot_size", 0.1)
            )
            
            # Set exit info if closed
            if trade.get("status") == TradeStatus.CLOSED.value:
                trade_obj.exit_price = trade.get("exit_price")
                trade_obj.exit_time = datetime.fromisoformat(trade.get("exit_time", ""))
                trade_obj.exit_reason = trade.get("exit_reason")
                trade_obj.profit = trade.get("profit")
                trade_obj.profit_percent = trade.get("profit_percent")
                trade_obj.status = TradeStatus.CLOSED
            
            async with TelegramSender() as sender:
                if trade.get("status") == TradeStatus.OPEN.value:
                    result = await sender.send_trade_opened(trade_obj)
                else:
                    result = await sender.send_trade_closed(trade_obj)
                
                return result is not None and result.get("ok", False)
                
        except Exception as e:
            logger.error(f"Failed to send trade to Telegram: {e}")
            return False
    
    async def run_trading_cycle(self) -> Dict[str, Any]:
        """Run a complete trading cycle"""
        cycle_start = datetime.utcnow()
        result = {
            "status": "started",
            "timestamp": cycle_start.isoformat(),
            "cycle_time": 0.0
        }
        
        try:
            # Step 1: Fetch market data
            logger.debug("Fetching market data...")
            data = await self.fetch_market_data()
            
            # Step 2: Analyze market
            logger.debug("Analyzing market...")
            analysis = await self.analyze_market(data)
            
            # Step 3: Generate signal
            logger.debug("Generating signal...")
            signal = await self.generate_signal(analysis)
            
            # Step 4: Execute trade if signal is strong enough
            executed_trade = None
            if signal and signal.get("strength", 0) >= 0.6:
                logger.debug("Executing trade...")
                executed_trade = await self.execute_trade(signal)
            
            # Step 5: Check existing trades
            logger.debug("Checking existing trades...")
            current_price = data.get("price", {}).bid if data.get("price") else None
            if current_price:
                closed_trades = await self.check_trades(current_price)
            else:
                closed_trades = []
            
            # Step 6: Send signals to Telegram
            if signal and config.telegram.BOT_TOKEN:
                await self.send_signal_to_telegram(signal)
            
            if executed_trade and config.telegram.BOT_TOKEN:
                await self.send_trade_to_telegram(executed_trade)
            
            for trade in closed_trades:
                if config.telegram.BOT_TOKEN:
                    await self.send_trade_to_telegram(trade)
            
            # Update result
            cycle_end = datetime.utcnow()
            result.update({
                "status": "completed",
                "cycle_time": (cycle_end - cycle_start).total_seconds(),
                "current_price": current_price,
                "signal": signal,
                "executed_trade": executed_trade,
                "closed_trades": closed_trades,
                "daily_stats": self.daily_stats.copy(),
                "open_trades": len(self.strategy.open_trades),
                "risk_status": self._get_risk_status()
            })
            
            logger.info(f"Cycle completed in {result['cycle_time']:.2f}s | "
                       f"Signal: {signal.get('direction', 'None') if signal else 'None'} | "
                       f"Trades: {self.daily_stats['trades']}/{config.trading.DAILY_TRADES_LIMIT}")
            
        except Exception as e:
            logger.error(f"Trading cycle failed: {e}")
            result.update({
                "status": "error",
                "error": str(e),
                "cycle_time": (datetime.utcnow() - cycle_start).total_seconds()
            })
        
        return result
    
    def _get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status"""
        report = self.risk_manager.get_risk_report()
        return {
            "risk_level": report.get("risk_level", "LOW"),
            "should_stop": report.get("should_stop_trading", False),
            "drawdown": report.get("metrics", {}).get("current_drawdown", 0),
            "account_balance": report.get("metrics", {}).get("account_balance", 0)
        }
    
    async def run_continuous(self, interval: float = 60.0):
        """Run continuous trading with specified interval (seconds)"""
        self.is_running = True
        logger.info(f"Starting continuous trading with {interval}s interval")
        
        try:
            while self.is_running:
                # Check if we should stop trading
                should_stop, reason = self.risk_manager.should_stop_trading()
                if should_stop:
                    logger.warning(f"Stopping trading: {reason}")
                    self.is_running = False
                    break
                
                # Check if it's a new day
                self.strategy._check_new_day()
                
                # Run trading cycle
                await self.run_trading_cycle()
                
                # Wait for next cycle
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, stopping...")
            self.is_running = False
        except Exception as e:
            logger.error(f"Continuous trading failed: {e}")
            self.is_running = False
        
        logger.info("Continuous trading stopped")
    
    async def run_daily_session(self):
        """Run a daily trading session (until daily limit or market close)"""
        self.is_running = True
        logger.info("Starting daily trading session")
        
        try:
            while self.is_running:
                # Check daily limits
                if self.daily_stats["trades"] >= config.trading.DAILY_TRADES_LIMIT:
                    logger.info(f"Daily trade limit reached ({self.daily_stats['trades']}/{config.trading.DAILY_TRADES_LIMIT})")
                    self.is_running = False
                    break
                
                # Check risk limits
                should_stop, reason = self.risk_manager.should_stop_trading()
                if should_stop:
                    logger.warning(f"Stopping trading: {reason}")
                    self.is_running = False
                    break
                
                # Run trading cycle
                result = await self.run_trading_cycle()
                
                # Check if market is closed (simple check - XAUUSD trades 24/5)
                now = datetime.utcnow()
                if now.weekday() >= 5:  # Saturday or Sunday
                    logger.info("Weekend detected, stopping trading")
                    self.is_running = False
                    break
                
                # Small delay between cycles
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, stopping...")
            self.is_running = False
        except Exception as e:
            logger.error(f"Daily session failed: {e}")
            self.is_running = False
        
        # Send daily summary
        if config.telegram.BOT_TOKEN:
            await self._send_daily_summary()
        
        logger.info("Daily trading session stopped")
    
    async def _send_daily_summary(self):
        """Send daily summary to Telegram"""
        try:
            async with TelegramSender() as sender:
                await sender.send_daily_summary(
                    self.strategy.closed_trades,
                    self.daily_stats["profit"] - self.daily_stats["loss"],
                    self.daily_stats["trades"]
                )
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        uptime = datetime.utcnow() - self.start_time
        
        return {
            "name": self.name,
            "version": self.version,
            "is_running": self.is_running,
            "uptime": str(uptime),
            "start_time": self.start_time.isoformat(),
            "trade_count": self.trade_count,
            "signal_count": self.signal_count,
            "daily_stats": self.daily_stats,
            "open_trades": len(self.strategy.open_trades),
            "closed_trades": len(self.strategy.closed_trades),
            "risk_status": self._get_risk_status()
        }
    
    def stop(self):
        """Stop the bot"""
        self.is_running = False
        logger.info("Bot stopped")


# Global bot instance
bot = VIPBot()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="VIP.BOT - Professional XAUUSD Trading Bot")
    parser.add_argument("--test", action="store_true", help="Run test and exit")
    parser.add_argument("--continuous", action="store_true", help="Run continuous trading")
    parser.add_argument("--daily", action="store_true", help="Run daily session")
    parser.add_argument("--interval", type=float, default=60.0, help="Interval in seconds for continuous mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize bot
    await bot.initialize()
    
    if args.test:
        # Run a single test cycle
        logger.info("Running test cycle...")
        result = await bot.run_trading_cycle()
        print("\nTest Cycle Result:")
        for key, value in result.items():
            if isinstance(value, (dict, list)):
                print(f"  {key}: {type(value).__name__} with {len(value) if hasattr(value, '__len__') else 'N/A'} items")
            else:
                print(f"  {key}: {value}")
        
        # Print status
        print("\nBot Status:")
        status = bot.get_status()
        for key, value in status.items():
            if key != "uptime":
                print(f"  {key}: {value}")
        
    elif args.continuous:
        # Run continuous trading
        await bot.run_continuous(interval=args.interval)
    
    elif args.daily:
        # Run daily session
        await bot.run_daily_session()
    
    else:
        # Default: run a few cycles and exit
        logger.info("Running default mode (5 cycles)...")
        for i in range(5):
            result = await bot.run_trading_cycle()
            logger.info(f"Cycle {i+1} completed")
            await asyncio.sleep(2)
        
        # Print final status
        print("\nFinal Status:")
        status = bot.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())

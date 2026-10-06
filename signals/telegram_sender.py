"""
Telegram Signal Sender - Sends trading signals to Telegram
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from config.settings import config
from strategies.scalping_strategy import TradeSignal, Trade, TradeStatus

logger = logging.getLogger(__name__)


@dataclass
class TelegramMessage:
    """Represents a Telegram message"""
    message_id: Optional[int] = None
    chat_id: Optional[str] = None
    text: str = ""
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True
    reply_markup: Optional[Dict] = None


class TelegramSender:
    """Sends messages to Telegram channels/bots"""
    
    def __init__(self):
        self.bot_token = config.telegram.BOT_TOKEN
        self.channel_id = config.telegram.CHANNEL_ID
        self.admin_id = config.telegram.ADMIN_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.message_counter = 0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _send_request(
        self, 
        method: str, 
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Send request to Telegram API"""
        url = f"{self.base_url}/{method}"
        
        try:
            async with self.session.post(url, params=params, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Telegram API error: {response.status}")
                    return {"ok": False, "error": f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"Failed to send Telegram request: {e}")
            return {"ok": False, "error": str(e)}
    
    async def send_message(
        self, 
        text: str, 
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Send a text message"""
        if not chat_id:
            chat_id = self.channel_id
        
        if not chat_id:
            logger.warning("No chat ID configured, cannot send message")
            return None
        
        params = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": str(disable_web_page_preview).lower()
        }
        
        result = await self._send_request("sendMessage", params=params)
        
        if result.get("ok"):
            self.message_counter += 1
            logger.info(f"Message sent to {chat_id}: {text[:50]}...")
        else:
            logger.error(f"Failed to send message: {result.get('description', result.get('error', 'Unknown error'))}")
        
        return result
    
    def _format_signal_message(self, signal: TradeSignal) -> str:
        """Format a trading signal message for Telegram"""
        direction_emoji = "🟢" if signal.direction.value == "BUY" else "🔴"
        direction_text = "شِرَاء" if signal.direction.value == "BUY" else "بَيْع"
        
        # Calculate risk-reward ratio
        if signal.direction.value == "BUY":
            risk = signal.entry_price - signal.stop_loss
            reward = signal.take_profit - signal.entry_price
        else:
            risk = signal.stop_loss - signal.entry_price
            reward = signal.entry_price - signal.take_profit
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        message = f"""
{direction_emoji} <b>إشارة تداول جديدة</b> {direction_emoji}

<b>📊 الاتجاه:</b> {direction_text}
<b>💰 سعر الدخول:</b> {signal.entry_price:.2f}
<b>⛔ ستوب لوس:</b> {signal.stop_loss:.2f}
<b>🎯 تيك بروفيت:</b> {signal.take_profit:.2f}

<b>📈 نسبة المخاطرة/الربح:</b> {rr_ratio:.2f}:1
<b>💪 قوة الإشارة:</b> {signal.strength * 100:.1f}%
<b>🎯 ثقة الإشارة:</b> {signal.confidence * 100:.1f}%

<b>🔍 سبب الدخول:</b>
{signal.reason}

<b>📊 المؤشرات:</b>
"""
        
        for name, value in signal.indicators.items():
            if name == "RSI":
                rsi_status = "مُشْتَرى" if value > 70 else "مُبَاع" if value < 30 else "مُعْتَدِل"
                message += f"• RSI: {value:.2f} ({rsi_status})\n"
            elif name == "MACD":
                message += f"• MACD: {value:.4f}\n"
            elif name == "Stochastic_K":
                message += f"• Stochastic: {value:.2f}\n"
            elif name == "ATR":
                message += f"• ATR: {value:.2f}\n"
        
        if signal.patterns:
            message += f"\n<b>🔄 الأنماط:</b> {', '.join(signal.patterns)}\n"
        
        message += f"\n<b>⏰ الوقت:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return message
    
    def _format_trade_open_message(self, trade: Trade) -> str:
        """Format message for trade opened"""
        direction_emoji = "🟢" if trade.direction.value == "BUY" else "🔴"
        direction_text = "شِرَاء" if trade.direction.value == "BUY" else "بَيْع"
        
        message = f"""
{direction_emoji} <b>تم فتح صفقة جديدة</b> {direction_emoji}

<b>📋 رقم الصفقة:</b> {trade.trade_id}
<b>💰 سعر الدخول:</b> {trade.entry_price:.2f}
<b>⛔ ستوب لوس:</b> {trade.stop_loss:.2f}
<b>🎯 تيك بروفيت:</b> {trade.take_profit:.2f}
<b>📊 حجم الصفقة:</b> {trade.lot_size}

<b>⏰ وقت الفتح:</b> {trade.entry_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        return message
    
    def _format_trade_close_message(self, trade: Trade) -> str:
        """Format message for trade closed"""
        direction_emoji = "🟢" if trade.direction.value == "BUY" else "🔴"
        direction_text = "شِرَاء" if trade.direction.value == "BUY" else "بَيْع"
        
        profit_emoji = "💰" if trade.profit and trade.profit > 0 else "💔"
        profit_text = "رَبْح" if trade.profit and trade.profit > 0 else "خَسَارَة"
        
        message = f"""
{direction_emoji} <b>تم إغلاق الصفقة</b> {direction_emoji}

<b>📋 رقم الصفقة:</b> {trade.trade_id}
<b>💰 سعر الدخول:</b> {trade.entry_price:.2f}
<b>💰 سعر الخروج:</b> {trade.exit_price:.2f if trade.exit_price else 'N/A'}
<b>📊 النتيجة:</b> {profit_emoji} {abs(trade.profit):.2f} USD ({profit_text})
<b>📈 نسبة الربح:</b> {trade.profit_percent:.2f}%
<b>🔍 سبب الإغلاق:</b> {trade.exit_reason or 'N/A'}

<b>⏰ وقت الفتح:</b> {trade.entry_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
<b>⏰ وقت الإغلاق:</b> {trade.exit_time.strftime('%Y-%m-%d %H:%M:%S UTC') if trade.exit_time else 'N/A'}
"""
        
        return message
    
    def _format_daily_summary(self, 
        trades: List[Trade], 
        daily_profit: float,
        daily_trades: int
    ) -> str:
        """Format daily summary message"""
        winning_trades = sum(1 for t in trades if t.profit is not None and t.profit > 0)
        losing_trades = sum(1 for t in trades if t.profit is not None and t.profit < 0)
        total_profit = sum(t.profit for t in trades if t.profit is not None and t.profit > 0)
        total_loss = sum(abs(t.profit) for t in trades if t.profit is not None and t.profit < 0)
        
        win_rate = winning_trades / (winning_trades + losing_trades) * 100 if (winning_trades + losing_trades) > 0 else 0
        
        message = f"""
📊 <b>ملخص اليوم التداولي</b>

<b>📈 إحصائيات:</b>
• عدد الصفقات: {daily_trades}/{config.trading.DAILY_TRADES_LIMIT}
• صفقات رابحة: {winning_trades}
• صفقات خاسرة: {losing_trades}
• نسبة النجاح: {win_rate:.1f}%

<b>💰 الأرباح:</b>
• إجمالي الأرباح: 💰 {total_profit:.2f} USD
• إجمالي الخسائر: 💔 {total_loss:.2f} USD
• صافي اليوم: {'💰' if daily_profit >= 0 else '💔'} {daily_profit:.2f} USD

<b>🎯 الهدف:</b> {config.trading.DAILY_TRADES_LIMIT} صفقة يومياً
<b>⏰ الوقت:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        return message
    
    def _format_aggressive_signal(self, signal: TradeSignal) -> str:
        """Format aggressive signal with emphasis"""
        direction_emoji = "🟢🟢🟢" if signal.direction.value == "BUY" else "🔴🔴🔴"
        direction_text = "شِرَاء عدواني" if signal.direction.value == "BUY" else "بَيْع عدواني"
        
        message = f"""
{direction_emoji}
<b>⚡ إشَارَة عَدْوَانِيَّة ⚡</b>
{direction_emoji}

<b>🎯 هذا وقت للدخول بقوة!</b>

<b>📊 الاتجاه:</b> {direction_text}
<b>💰 سعر الدخول:</b> <code>{signal.entry_price:.2f}</code>
<b>⛔ ستوب لوس:</b> <code>{signal.stop_loss:.2f}</code>
<b>🎯 تيك بروفيت:</b> <code>{signal.take_profit:.2f}</code>

<b>💪 قوة الإشارة:</b> <b>{signal.strength * 100:.1f}%</b> ⭐
<b>🎯 ثقة الإشارة:</b> <b>{signal.confidence * 100:.1f}%</b> ✅

<b>🔥 سبب الدخول:</b>
{signal.reason}

<b>📊 المؤشرات:</b>
"""
        
        for name, value in signal.indicators.items():
            if name == "RSI":
                rsi_status = "مُشْتَرى إلى حد كبير" if value > 70 else "مُبَاع إلى حد كبير" if value < 30 else "مُعْتَدِل"
                message += f"• RSI: <b>{value:.2f}</b> ({rsi_status})\n"
            elif name == "MACD":
                message += f"• MACD: <b>{value:.4f}</b>\n"
        
        if signal.patterns:
            message += f"\n<b>🔄 أنماط قوية:</b> {', '.join(signal.patterns)}\n"
        
        message += f"\n<b>⏰ الوقت:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        message += "\n<b>⚠️ تحذير: هذه إشارة عدوانية مع مخاطرة عالية، ولكن مع احتمال ربح كبير</b>"
        
        return message
    
    async def send_signal(self, signal: TradeSignal) -> Optional[Dict[str, Any]]:
        """Send a trading signal to Telegram"""
        if not self.channel_id or not self.bot_token:
            logger.warning("Telegram not configured, cannot send signal")
            return None
        
        # Format message based on signal strength
        if signal.strength >= 0.8:
            message = self._format_aggressive_signal(signal)
        else:
            message = self._format_signal_message(signal)
        
        return await self.send_message(message)
    
    async def send_trade_opened(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Send notification when a trade is opened"""
        if not self.channel_id or not self.bot_token:
            return None
        
        message = self._format_trade_open_message(trade)
        return await self.send_message(message)
    
    async def send_trade_closed(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Send notification when a trade is closed"""
        if not self.channel_id or not self.bot_token:
            return None
        
        message = self._format_trade_close_message(trade)
        return await self.send_message(message)
    
    async def send_daily_summary(
        self, 
        trades: List[Trade], 
        daily_profit: float,
        daily_trades: int
    ) -> Optional[Dict[str, Any]]:
        """Send daily trading summary"""
        if not self.channel_id or not self.bot_token:
            return None
        
        message = self._format_daily_summary(trades, daily_profit, daily_trades)
        return await self.send_message(message)
    
    async def send_alert(self, message: str) -> Optional[Dict[str, Any]]:
        """Send an alert message"""
        if not self.admin_id or not self.bot_token:
            logger.warning("Admin ID not configured, cannot send alert")
            return None
        
        formatted_message = f"⚠️ <b>تنبيه مهم</b>\n\n{message}"
        return await self.send_message(formatted_message, chat_id=self.admin_id)
    
    async def send_to_admin(self, message: str) -> Optional[Dict[str, Any]]:
        """Send a message to admin"""
        if not self.admin_id or not self.bot_token:
            return None
        
        return await self.send_message(message, chat_id=self.admin_id)
    
    async def broadcast(self, message: str) -> List[Dict[str, Any]]:
        """Broadcast message to all configured channels"""
        results = []
        
        # Send to main channel
        if self.channel_id:
            result = await self.send_message(message, chat_id=self.channel_id)
            results.append(result)
        
        # Send to admin
        if self.admin_id and self.admin_id != self.channel_id:
            result = await self.send_message(message, chat_id=self.admin_id)
            results.append(result)
        
        return results


# Global instance
telegram_sender = TelegramSender()


async def test_telegram():
    """Test Telegram connection"""
    from strategies.scalping_strategy import TradeSignal, TradeDirection
    
    # Create a test signal
    signal = TradeSignal(
        signal_id="TEST_001",
        timestamp=datetime.utcnow(),
        direction=TradeDirection.BUY,
        entry_price=2000.50,
        stop_loss=1995.00,
        take_profit=2010.00,
        confidence=0.95,
        strength=0.9,
        reason="Strong bullish momentum with RSI oversold and MACD crossover",
        indicators={"RSI": 25.0, "MACD": 0.5, "Stochastic_K": 20.0},
        patterns=["Bullish Engulfing", "Hammer"],
        timeframe="1m"
    )
    
    async with TelegramSender() as sender:
        # Test if bot token is configured
        if not sender.bot_token:
            print("⚠️ Telegram bot token not configured")
            print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID environment variables")
            return False
        
        # Test message
        test_msg = "✅ اختبار اتصال تلجرام - VIP.BOT يعمل بشكل صحيح"
        result = await sender.send_message(test_msg)
        
        if result and result.get("ok"):
            print("✓ Telegram connection OK")
            
            # Send signal test
            signal_result = await sender.send_signal(signal)
            if signal_result and signal_result.get("ok"):
                print("✓ Signal message sent successfully")
            else:
                print("✗ Failed to send signal message")
            
            return True
        else:
            print(f"✗ Telegram connection failed: {result}")
            return False


if __name__ == "__main__":
    asyncio.run(test_telegram())

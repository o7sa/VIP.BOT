"""
Telegram Signal Sender - Beautiful Arabic formatted messages
"""

import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from config.settings import config
from strategies.scalping_strategy import TradeSignal, Trade, TradeDirection, TradeStatus

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self):
        self.token = config.telegram.BOT_TOKEN
        self.channel = config.telegram.CHANNEL_ID
        self.admin = config.telegram.ADMIN_ID
        self.session: Optional[aiohttp.ClientSession] = None
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
            self.session = None

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.channel)

    async def send_message(self, text: str, chat_id: str = None) -> Optional[Dict]:
        if not self.is_configured:
            return None
        target = chat_id or self.channel
        try:
            async with self.session.post(
                f"{self.base}/sendMessage",
                json={
                    "chat_id": target,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.warning(f"Telegram error: {data}")
                return data
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return None

    async def send_signal(self, signal: TradeSignal) -> Optional[Dict]:
        dir_emoji = "\U0001f7e2" if signal.direction == TradeDirection.BUY else "\U0001f534"
        dir_ar = "\u0634\u0631\u0627\u0621" if signal.direction == TradeDirection.BUY else "\u0628\u064a\u0639"
        stars = "\u2b50" * min(5, int(signal.strength * 5) + 1)
        text = f"""
{dir_emoji} <b>\u0625\u0634\u0627\u0631\u0629 VIP.BOT</b> {dir_emoji}

\U0001f3af <b>\u0627\u0644\u0627\u062a\u062c\u0627\u0647:</b> {dir_ar} \u0639\u062f\u0648\u0627\u0646\u064a
\U0001f4b0 <b>\u0633\u0639\u0631 \u0627\u0644\u062f\u062e\u0648\u0644:</b> <code>{signal.entry_price:.2f}</code>
\u26d4 <b>\u0633\u062a\u0648\u0628 \u0644\u0648\u0633:</b> <code>{signal.stop_loss:.2f}</code>
\U0001f3af <b>\u062a\u064a\u0643 \u0628\u0631\u0648\u0641\u064a\u062a:</b> <code>{signal.take_profit:.2f}</code>

\U0001f4aa <b>\u0642\u0648\u0629 \u0627\u0644\u0625\u0634\u0627\u0631\u0629:</b> {signal.strength*100:.0f}% {stars}
\u2705 <b>\u0627\u0644\u062b\u0642\u0629:</b> {signal.confidence*100:.0f}%

\U0001f4ca <b>\u0633\u0628\u0628 \u0627\u0644\u062f\u062e\u0648\u0644:</b>
{signal.reason}

\U0001f56f <b>\u0623\u0646\u0645\u0627\u0637 \u0627\u0644\u0634\u0645\u0648\u0639:</b> {', '.join(signal.patterns) if signal.patterns else '\u2014'}

\u23f0 {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        return await self.send_message(text.strip())

    async def send_trade_opened(self, trade: Trade) -> Optional[Dict]:
        dir_ar = "\u0634\u0631\u0627\u0621" if trade.direction == TradeDirection.BUY else "\u0628\u064a\u0639"
        text = f"""
\u2705 <b>\u062a\u0645 \u0641\u062a\u062d \u0635\u0641\u0642\u0629</b>

\U0001f194 <code>{trade.trade_id}</code>
\U0001f4c8 {dir_ar} @ <code>{trade.entry_price:.2f}</code>
\u26d4 SL: <code>{trade.stop_loss:.2f}</code> | \U0001f3af TP: <code>{trade.take_profit:.2f}</code>
\U0001f4dd {trade.reason}
"""
        return await self.send_message(text.strip())

    async def send_trade_closed(self, trade: Trade) -> Optional[Dict]:
        profit = trade.profit or 0
        emoji = "\u2705" if profit >= 0 else "\u274c"
        text = f"""
{emoji} <b>\u062a\u0645 \u0625\u063a\u0644\u0627\u0642 \u0635\u0641\u0642\u0629</b>

\U0001f194 <code>{trade.trade_id}</code>
\U0001f4b0 \u0627\u0644\u0631\u0628\u062d/\u0627\u0644\u062e\u0633\u0627\u0631\u0629: <b>{profit:+.2f}</b>
\U0001f4cc \u0627\u0644\u0633\u0628\u0628: {trade.exit_reason}
\u23f1 \u0627\u0644\u0645\u062f\u0629: {((trade.exit_time or datetime.utcnow()) - trade.entry_time).seconds // 60} \u062f\u0642\u064a\u0642\u0629
"""
        return await self.send_message(text.strip())


telegram_sender = TelegramSender()

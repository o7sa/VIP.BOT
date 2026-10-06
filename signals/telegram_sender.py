"""
Telegram Signal Sender + simple /start command handler
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from config.settings import config
from strategies.scalping_strategy import TradeSignal, Trade, TradeDirection, TradeStatus

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self):
        self.token = (config.telegram.BOT_TOKEN or "").strip()
        ch = (config.telegram.CHANNEL_ID or "").strip()
        if ch and not ch.startswith("@") and not ch.startswith("-") and not ch.lstrip("-").isdigit():
            ch = f"@{ch}"
        self.channel = ch
        adm = (config.telegram.ADMIN_ID or "").strip()
        adm = "".join(c for c in adm if c.isdigit() or c == "-")
        self.admin = adm
        self.session: Optional[aiohttp.ClientSession] = None
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self._offset = 0
        self._poll_task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
            self.session = None

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.channel)

    async def _ensure_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def send_message(self, text: str, chat_id: str = None) -> Optional[Dict]:
        if not self.token:
            return None
        await self._ensure_session()
        target = chat_id or self.channel
        if not target:
            return None
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
\U0001f4b0 \u0627\u0644\u0646\u062a\u064a\u062c\u0629: <code>{profit:+.2f}</code>
\U0001f4dd \u0627\u0644\u0633\u0628\u0628: {trade.exit_reason or '\u2014'}
"""
        return await self.send_message(text.strip())

    async def send_start_reply(self, chat_id: str):
        text = """
\U0001f916 <b>VIP.BOT \u062c\u0627\u0647\u0632</b>

\u0627\u0644\u0628\u0648\u062a \u064a\u0639\u0645\u0644 \u0627\u0644\u0622\u0646 \u0648\u064a\u062d\u0644\u0644 \u0634\u0645\u0648\u0639 \u0627\u0644\u0630\u0647\u0628 XAUUSD.

\u2705 \u064a\u0631\u0633\u0644 \u0627\u0644\u0625\u0634\u0627\u0631\u0627\u062a \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b \u0644\u0644\u0642\u0646\u0627\u0629 \u0639\u0646\u062f \u0648\u062c\u0648\u062f \u0641\u0631\u0635\u0629
\U0001f56f \u064a\u0639\u062a\u0645\u062f \u0639\u0644\u0649 \u0627\u0644\u0634\u0645\u0648\u0639 \u0627\u0644\u064a\u0627\u0628\u0627\u0646\u064a\u0629 \u0623\u0648\u0644\u0627\u064b
\U0001f4ca \u0627\u0644\u0648\u0627\u062c\u0647\u0629 \u0627\u0644\u0632\u062c\u0627\u062c\u064a\u0629 \u0645\u062a\u0627\u062d\u0629 \u0639\u0644\u0649 \u0627\u0644\u0633\u064a\u0631\u0641\u0631

\u0623\u0631\u0633\u0644 /status \u0644\u0645\u0639\u0631\u0641\u0629 \u062d\u0627\u0644\u0629 \u0627\u0644\u0628\u0648\u062a
"""
        await self.send_message(text.strip(), chat_id=chat_id)

    async def send_status_reply(self, chat_id: str, status: Dict[str, Any]):
        price = status.get("price") or {}
        mid = price.get("mid") or price.get("bid") or "\u2014"
        text = f"""
\U0001f4ca <b>\u062d\u0627\u0644\u0629 VIP.BOT</b>

\U0001f4b0 \u0627\u0644\u0633\u0639\u0631: <code>{mid}</code>
\U0001f504 \u0627\u0644\u062f\u0648\u0631\u0629: {status.get('cycle_count', 0)}
\U0001f4c8 \u0635\u0641\u0642\u0627\u062a \u0645\u0641\u062a\u0648\u062d\u0629: {status.get('open_trades_count', 0)}
\U0001f4c5 \u0635\u0641\u0642\u0627\u062a \u0627\u0644\u064a\u0648\u0645: {status.get('daily_trades', 0)}/{status.get('daily_limit', 25)}
\U0001f6e1 \u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u0645\u062e\u0627\u0637\u0631: {status.get('risk_level', '\u2014')}
"""
        await self.send_message(text.strip(), chat_id=chat_id)

    async def _handle_updates(self, status_provider=None):
        await self._ensure_session()
        while True:
            try:
                async with self.session.get(
                    f"{self.base}/getUpdates",
                    params={"offset": self._offset, "timeout": 25, "allowed_updates": ["message"]}
                ) as resp:
                    data = await resp.json()
                if not data.get("ok"):
                    await asyncio.sleep(3)
                    continue
                for upd in data.get("result", []):
                    self._offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    text = (msg.get("text") or "").strip()
                    chat = msg.get("chat") or {}
                    chat_id = str(chat.get("id", ""))
                    if not chat_id:
                        continue
                    if text.startswith("/start"):
                        await self.send_start_reply(chat_id)
                    elif text.startswith("/status") and status_provider:
                        try:
                            st = status_provider()
                            await self.send_status_reply(chat_id, st)
                        except Exception as e:
                            logger.error(f"status reply error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telegram poll error: {e}")
                await asyncio.sleep(5)

    def start_polling(self, status_provider=None):
        if not self.token:
            logger.warning("Telegram token missing \u2013 polling disabled")
            return
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._handle_updates(status_provider))
        logger.info("Telegram command polling started (/start, /status)")

    async def stop_polling(self):
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None


telegram_sender = TelegramSender()

"""
Telegram Signal Sender - Professional format
TP1 / TP2 / TP3 + BE management messages
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from config.settings import config
from strategies.scalping_strategy import TradeSignal, Trade, TradeDirection

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
                json={"chat_id": target, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.warning(f"Telegram error: {data}")
                return data
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return None

    async def send_signal(self, signal: TradeSignal) -> Optional[Dict]:
        is_buy = signal.direction == TradeDirection.BUY
        header = "\U0001f7e2 +BUY - QUALITY \u0625\u0634\u0627\u0631\u0629" if is_buy else "\U0001f534 +SELL - QUALITY \u0625\u0634\u0627\u0631\u0629"
        sl_dist = abs(signal.entry_price - signal.stop_loss)
        text = f"""
{header}

\U0001f194 <code>{signal.signal_id}</code>
\u26a1 \u0627\u0644\u062f\u062e\u0648\u0644: <b>{signal.entry_price:.3f}</b>

\U0001f534 SL: <code>{signal.stop_loss:.2f}</code> ({sl_dist:.2f})
\U0001f3af TP1: <code>{signal.tp1:.2f}</code>
\U0001f680 TP2: <code>{signal.tp2:.2f}</code>
\U0001f3c6 TP3: <code>{signal.tp3:.2f}</code>

\U0001f4ca A \u2705 | Score: <b>{signal.score}/100</b>
\U0001f4c8 RSI: {signal.indicators.get('rsi', '\u2014')}
\U0001f56f \u0627\u0644\u0646\u0645\u0637: <b>{signal.pattern_name or '\u2014'}</b>
\U0001f9e0 {signal.multi_tf or ''}
\U0001f4cc {signal.reason}
"""
        return await self.send_message(text.strip())

    async def send_tp1_secured(self, trade: Trade) -> Optional[Dict]:
        side = "BUY" if trade.direction == TradeDirection.BUY else "SELL"
        text = f"""
\u2705 <b>\u062a\u0623\u0645\u064a\u0646 TP1 - {side}</b>

\u0627\u0644\u062f\u062e\u0648\u0644: <code>{trade.entry_price:.3f}</code>
\u0627\u0644\u0633\u0639\u0631: <code>{trade.tp1:.3f}</code>
\U0001f6e1 SL \u0627\u0644\u062c\u062f\u064a\u062f: <code>{trade.stop_loss:.2f}</code>
\U0001f680 \u0646\u0643\u0645\u0644 \u0625\u0644\u0649 TP2: <code>{trade.tp2:.2f}</code>
"""
        return await self.send_message(text.strip())

    async def send_tp2_secured(self, trade: Trade) -> Optional[Dict]:
        is_buy = trade.direction == TradeDirection.BUY
        side = "BUY" if is_buy else "SELL"
        floating = (trade.tp2 - trade.entry_price) if is_buy else (trade.entry_price - trade.tp2)
        text = f"""
\U0001f680 <b>TP2 - {side} - \u0645\u0624\u0645\u0646 \u2705</b>
+{floating:.2f}
\U0001f6e1 SL: <code>{trade.stop_loss:.2f}</code>
\U0001f3c6 \u0645\u0643\u0645\u0644\u064a\u0646 \u0644\u0640 TP3: <code>{trade.tp3:.2f}</code>
"""
        return await self.send_message(text.strip())

    async def send_tp3_hit(self, trade: Trade) -> Optional[Dict]:
        side = "BUY" if trade.direction == TradeDirection.BUY else "SELL"
        profit = trade.profit or 0
        text = f"""
\U0001f3c6 <b>TP3 - {side} - \u0647\u062f\u0641 \u0643\u0627\u0645\u0644</b>
+{profit:.2f}
"""
        return await self.send_message(text.strip())

    async def send_be_closed(self, trade: Trade) -> Optional[Dict]:
        side = "BUY" if trade.direction == TradeDirection.BUY else "SELL"
        profit = trade.profit or 0
        mins = 0
        if trade.exit_time and trade.entry_time:
            mins = int((trade.exit_time - trade.entry_time).total_seconds() / 60)
        text = f"""
\U0001f6e1 <b>BE - {side}</b>
\u0627\u0644\u062f\u062e\u0648\u0644: <code>{trade.entry_price:.3f}</code>
\u0627\u0644\u062e\u0631\u0648\u062c: <code>{trade.exit_price:.3f}</code>
{profit:+.2f}
\u062f{mins}
"""
        return await self.send_message(text.strip())

    async def send_trade_closed(self, trade: Trade, event: str = None) -> Optional[Dict]:
        if event == "TP1":
            return await self.send_tp1_secured(trade)
        if event == "TP2":
            return await self.send_tp2_secured(trade)
        if event == "TP3":
            return await self.send_tp3_hit(trade)
        if event == "BE":
            return await self.send_be_closed(trade)
        profit = trade.profit or 0
        emoji = "\u2705" if profit >= 0 else "\u274c"
        side = "BUY" if trade.direction == TradeDirection.BUY else "SELL"
        text = f"""
{emoji} <b>\u0625\u063a\u0644\u0627\u0642 - {side}</b>
\U0001f194 <code>{trade.trade_id}</code>
\u0627\u0644\u062f\u062e\u0648\u0644: <code>{trade.entry_price:.3f}</code>
\u0627\u0644\u062e\u0631\u0648\u062c: <code>{trade.exit_price:.3f}</code>
\u0627\u0644\u0646\u062a\u064a\u062c\u0629: <b>{profit:+.2f}</b>
\u0627\u0644\u0633\u0628\u0628: {trade.exit_reason or '\u2014'}
"""
        return await self.send_message(text.strip())

    async def send_trade_opened(self, trade: Trade) -> Optional[Dict]:
        return None

    async def send_start_reply(self, chat_id: str):
        text = """
\U0001f916 <b>VIP.BOT \u062c\u0627\u0647\u0632</b>

\u0627\u0644\u0628\u0648\u062a \u064a\u0639\u0645\u0644 \u0627\u0644\u0622\u0646 \u0648\u064a\u062d\u0644\u0644 \u0634\u0645\u0648\u0639 \u0627\u0644\u0630\u0647\u0628 XAUUSD.

\u2705 \u0635\u0641\u0642\u0629 \u0648\u0627\u062d\u062f\u0629 \u0641\u0642\u0637 \u0641\u064a \u0646\u0641\u0633 \u0627\u0644\u0648\u0642\u062a
\U0001f56f \u064a\u0639\u062a\u0645\u062f \u0639\u0644\u0649 \u0622\u062e\u0631 15 \u0634\u0645\u0639\u0629 \u064a\u0627\u0628\u0627\u0646\u064a\u0629
\U0001f3af TP1 / TP2 / TP3 \u0645\u0639 \u062a\u0623\u0645\u064a\u0646 \u062a\u0644\u0642\u0627\u0626\u064a
\u23f1 \u0623\u0642\u0635\u0649 50 \u062f\u0642\u064a\u0642\u0629 \u0625\u0630\u0627 \u0643\u0627\u0646\u062a \u0627\u0644\u0635\u0641\u0642\u0629 \u062e\u0627\u0633\u0631\u0629

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
                            await self.send_status_reply(chat_id, status_provider())
                        except Exception as e:
                            logger.error(f"status reply error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telegram poll error: {e}")
                await asyncio.sleep(5)

    def start_polling(self, status_provider=None):
        if not self.token:
            return
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._handle_updates(status_provider))
        logger.info("Telegram polling started")

    async def stop_polling(self):
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None


telegram_sender = TelegramSender()

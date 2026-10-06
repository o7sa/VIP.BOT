"""
VIP.BOT - Main Application
Glass Dashboard + Aggressive Japanese Candlestick Scalper
Ready for Render deployment
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from config.settings import config
from modules.data_fetcher import BIQuoteClient, data_cache
from modules.technical_analyzer import technical_analyzer
from modules.pattern_detector import pattern_detector
from strategies.scalping_strategy import scalping_strategy, TradeDirection
from utils.risk_manager import risk_manager
from signals.telegram_sender import telegram_sender

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("VIP.BOT")


class VIPBotEngine:
    def __init__(self):
        self.running = False
        self.last_price: Optional[Dict] = None
        self.latest_patterns: List[Dict] = []
        self.last_cycle: Optional[Dict] = None
        self.cycle_count = 0
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("VIP.BOT Engine started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("VIP.BOT Engine stopped")

    async def _loop(self):
        interval = config.app.BOT_LOOP_INTERVAL
        while self.running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def _run_cycle(self):
        self.cycle_count += 1
        start = datetime.utcnow()
        result: Dict[str, Any] = {"cycle": self.cycle_count, "timestamp": start.isoformat()}

        can_trade, reason = risk_manager.can_open_trade(len(scalping_strategy.open_trades))
        if not can_trade:
            logger.warning(f"Trading paused: {reason}")
            result["status"] = "paused"
            result["reason"] = reason
            self.last_cycle = result
            return

        async with BIQuoteClient() as client:
            try:
                price = await data_cache.get_price(client)
                self.last_price = price.to_dict()
                current = price.mid
            except Exception as e:
                logger.error(f"Price fetch failed: {e}")
                return

            try:
                candles = await data_cache.get_candles(client, "1m", 200)
            except Exception as e:
                logger.error(f"Candles fetch failed: {e}")
                return

            if len(candles) < 30:
                logger.warning("Not enough candles")
                return

            analysis = technical_analyzer.analyze(candles, "1m")
            patterns = pattern_detector.detect_all_patterns(candles)
            self.latest_patterns = [p.to_dict() for p in patterns[:6]]

            for trade in list(scalping_strategy.open_trades):
                closed = scalping_strategy.check_exit(trade, current)
                if closed:
                    risk_manager.record_trade(trade)
                    if telegram_sender.is_configured:
                        async with telegram_sender as tg:
                            await tg.send_trade_closed(trade)

            risk_manager.update_open_trades(scalping_strategy.open_trades)

            signal = scalping_strategy.generate_signal(candles, analysis, current)
            executed = None
            if signal:
                executed = scalping_strategy.execute_signal(signal)
                if executed and telegram_sender.is_configured:
                    async with telegram_sender as tg:
                        await tg.send_signal(signal)
                        await tg.send_trade_opened(executed)

            elapsed = (datetime.utcnow() - start).total_seconds()
            result.update({
                "status": "ok",
                "price": current,
                "signal": signal.to_dict() if signal else None,
                "executed": executed.to_dict() if executed else None,
                "open_count": len(scalping_strategy.open_trades),
                "patterns_count": len(patterns),
                "elapsed": round(elapsed, 3)
            })
            self.last_cycle = result
            logger.info(
                f"Cycle #{self.cycle_count} | Price={current:.2f} | "
                f"Open={len(scalping_strategy.open_trades)} | "
                f"Patterns={len(patterns)} | {elapsed:.2f}s"
            )

    def get_status(self) -> Dict[str, Any]:
        risk = risk_manager.get_risk_report()
        metrics = risk.get("metrics", {})
        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "price": self.last_price,
            "open_trades": scalping_strategy.get_open_trades_dict(),
            "open_trades_count": len(scalping_strategy.open_trades),
            "closed_trades": scalping_strategy.get_closed_trades_dict(40),
            "daily_trades": scalping_strategy.daily_trades,
            "daily_limit": config.trading.DAILY_TRADES_LIMIT,
            "daily_pnl": metrics.get("daily_pnl", 0),
            "win_rate": metrics.get("win_rate", 0),
            "risk_level": risk.get("risk_level", "LOW"),
            "drawdown": metrics.get("current_drawdown", 0),
            "latest_patterns": self.latest_patterns,
            "last_cycle": self.last_cycle,
            "account_balance": metrics.get("account_balance", 10000),
            "version": "2.0.0-glass"
        }


engine = VIPBotEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("VIP.BOT Glass Edition starting...")
    logger.info(f"Telegram configured: {bool(config.telegram.BOT_TOKEN)}")
    logger.info(f"Channel: {config.telegram.CHANNEL_ID}")
    logger.info(f"Port: {config.web.PORT}")
    await engine.start()
    try:
        telegram_sender.start_polling(status_provider=engine.get_status)
    except Exception as e:
        logger.warning(f"Telegram polling not started: {e}")
    yield
    try:
        await telegram_sender.stop_polling()
    except Exception:
        pass
    await engine.stop()


app = FastAPI(title="VIP.BOT", version="2.0.0", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"Dashboard template error: {e}", exc_info=True)
        html = f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><title>VIP.BOT</title>
<style>body{{font-family:sans-serif;background:#0f0c29;color:#fff;padding:40px;text-align:center}}
a{{color:#00d4aa}}</style></head><body>
<h1>VIP.BOT</h1>
<p>\u0627\u0644\u0648\u0627\u062c\u0647\u0629 \u0627\u0644\u0632\u062c\u0627\u062c\u064a\u0629 \u062a\u062d\u062a \u0627\u0644\u062a\u062d\u0645\u064a\u0644...</p>
<p><a href="/api/status">\u062d\u0627\u0644\u0629 \u0627\u0644\u0628\u0648\u062a (JSON)</a></p>
<p><a href="/api/health">Health</a></p>
<pre style="text-align:left;max-width:600px;margin:20px auto;background:#1a1a2e;padding:16px;border-radius:8px;overflow:auto">{e}</pre>
</body></html>"""
        return HTMLResponse(content=html, status_code=200)


@app.get("/api/status")
async def api_status():
    try:
        return JSONResponse(engine.get_status())
    except Exception as e:
        logger.error(f"status error: {e}")
        return JSONResponse({"error": str(e), "running": engine.running}, status_code=200)


@app.get("/api/health")
async def health():
    return {"status": "ok", "running": engine.running, "time": datetime.utcnow().isoformat()}


@app.get("/api/price")
async def api_price():
    return engine.last_price or {}


@app.post("/api/start")
async def api_start():
    await engine.start()
    return {"status": "started"}


@app.post("/api/stop")
async def api_stop():
    await engine.stop()
    return {"status": "stopped"}


def main():
    port = config.web.PORT
    logger.info(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False
    )


if __name__ == "__main__":
    main()

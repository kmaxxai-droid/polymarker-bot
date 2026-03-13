from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .chatgpt_bridge import ChatGPTBridge
from .config import Settings
from .models import AiRecommendation
from .polymarket_client import MarketScanner, PolymarketClient
from .storage import BotStorage
from .trader import PolymarketTrader


class PolymarketTelegramBot:
    def __init__(
        self,
        settings: Settings,
        storage: BotStorage,
        client: PolymarketClient,
        scanner: MarketScanner,
        chatgpt: ChatGPTBridge,
        trader: PolymarketTrader,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.client = client
        self.scanner = scanner
        self.chatgpt = chatgpt
        self.trader = trader

    def build_app(self) -> Application:
        app = Application.builder().token(self.settings.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self.on_start))
        app.add_handler(CommandHandler("scan", self.on_scan))
        app.add_handler(CommandHandler("auto", self.on_auto))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))
        app.add_handler(CallbackQueryHandler(self.on_button))
        return app

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Бот готов. Команды:\n"
            "/scan — события с горизонтом до 14 дней (2 стратегии) + prompt для ChatGPT\n"
            "/auto on|off — автоисполнение рекомендаций"
        )

    async def on_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        raw = self.client.fetch_active_markets(limit=400)
        scanned = self.storage.already_scanned_market_ids()
        candidates = self.scanner.select_candidates(raw, self.settings.max_candidates, scanned)
        if not candidates:
            await update.message.reply_text("Не найдено новых кандидатов по фильтрам (<=14 дней).")
            return

        prompt = self.chatgpt.build_prompt(candidates)
        scan_id = f"scan-{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        self.storage.save_scan(scan_id, prompt, candidates)

        context.bot_data["last_scan_id"] = scan_id
        context.bot_data["last_scan_prices"] = {m.market_id: m.current_yes_price for m in candidates}

        await update.message.reply_text(
            f"Найдено {len(candidates)} кандидатов (горизонт до 14 дней).\n"
            f"Scan ID: {scan_id}\n\n"
            "Скопируй prompt ниже в ChatGPT и пришли JSON-ответ сюда одним сообщением:\n\n"
            f"```\n{prompt}\n```",
            parse_mode="Markdown",
        )

    async def on_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Использование: /auto on или /auto off")
            return
        mode = context.args[0].lower()
        context.bot_data["auto_mode"] = mode == "on"
        await update.message.reply_text(f"Auto mode: {'ON' if context.bot_data['auto_mode'] else 'OFF'}")

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (update.message.text or "").strip()
        try:
            recs = self.chatgpt.parse_recommendations(text)
        except json.JSONDecodeError:
            await update.message.reply_text("Это не JSON. Пришли JSON-массив рекомендаций от ChatGPT.")
            return
        except Exception as exc:
            await update.message.reply_text(f"Ошибка разбора рекомендаций: {exc}")
            return

        if not recs:
            await update.message.reply_text("Рекомендации пустые.")
            return

        scan_id = context.bot_data.get("last_scan_id")
        if scan_id:
            self.storage.save_recommendations(scan_id, recs)
            self.storage.mark_scan_reviewed(scan_id)

        top = sorted(recs, key=lambda x: x.expected_value, reverse=True)[:5]
        msg = "Топ рекомендаций:\n" + "\n".join(
            [
                f"- {r.market_id} {r.outcome}: EV={r.expected_value:.3f}, stake=${min(r.stake_usd, self.settings.bet_max_usd):.2f}, max_entry={r.max_entry_price:.3f}"
                for r in top
            ]
        )

        context.bot_data["last_recommendations"] = top
        auto_mode = context.bot_data.get("auto_mode", self.settings.auto_mode)

        if auto_mode:
            results = await self._execute(top, context)
            await update.message.reply_text(msg + "\n\n" + results)
            return

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Подтвердить ставку (Top-5)", callback_data="confirm_top5")]]
        )
        await update.message.reply_text(msg + "\n\nПодтвердить исполнение?", reply_markup=keyboard)

    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if query.data != "confirm_top5":
            await query.edit_message_text("Неизвестная команда")
            return

        top: list[AiRecommendation] = context.bot_data.get("last_recommendations", [])
        if not top:
            await query.edit_message_text("Нет рекомендаций для исполнения")
            return

        results = await self._execute(top, context)
        await query.edit_message_text(f"Исполнение завершено:\n{results}")

    async def _execute(self, recs: list[AiRecommendation], context: ContextTypes.DEFAULT_TYPE) -> str:
        rows: list[str] = []
        market_prices: dict[str, float] = context.bot_data.get("last_scan_prices", {})
        for rec in recs:
            market_price = float(market_prices.get(rec.market_id, rec.max_entry_price))
            trade = self.trader.place_bet(rec, market_price=market_price)
            self.storage.save_trade(rec.market_id, trade.tx_hash, trade.__dict__)
            rows.append(f"{rec.market_id}: {trade.status} ({trade.tx_hash}), market_price={market_price:.3f}")
        return "\n".join(rows)

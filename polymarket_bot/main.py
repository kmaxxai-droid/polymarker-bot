from __future__ import annotations

from bot.chatgpt_bridge import ChatGPTBridge
from bot.config import load_settings
from bot.polymarket_client import MarketScanner, PolymarketClient
from bot.storage import BotStorage
from bot.telegram_bot import PolymarketTelegramBot
from bot.trader import PolymarketTrader


def main() -> None:
    settings = load_settings()
    storage = BotStorage(settings.sqlite_path)
    client = PolymarketClient(settings.polymarket_gamma_url)
    scanner = MarketScanner(min_edge=settings.min_edge, max_liquidity_usd=settings.max_liquidity_usd)
    chatgpt = ChatGPTBridge()
    trader = PolymarketTrader(settings)

    app = PolymarketTelegramBot(settings, storage, client, scanner, chatgpt, trader).build_app()
    app.run_polling()


if __name__ == "__main__":
    main()

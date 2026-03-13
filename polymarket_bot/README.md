# Polymarket Telegram Bot

Телеграм-бот, который:
1. Сканирует рынки Polymarket через Gamma API.
2. Отбирает недооцененные low-liquidity лоты с горизонтом до 14 дней.
3. Анализирует 2 стратегии: value_edge и high_probability.
4. Генерирует prompt для ChatGPT с реальной рыночной ценой входа (current_yes_price).
5. Принимает JSON-рекомендации, хранит историю сканов/ответов и в ручном/auto режиме исполняет сделки с лимитом ставки до $10.

## Структура

```text
polymarket_bot/
├── main.py
├── requirements.txt
├── .env.example
├── README.md
├── abi/
│   └── bet_executor.json
├── data/
└── bot/
    ├── __init__.py
    ├── config.py
    ├── models.py
    ├── storage.py
    ├── polymarket_client.py
    ├── chatgpt_bridge.py
    ├── trader.py
    └── telegram_bot.py
```

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

> В `.env` укажите приватный ключ MetaMask-кошелька Polygon и Telegram токен.

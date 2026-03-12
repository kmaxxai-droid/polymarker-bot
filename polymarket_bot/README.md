# Polymarket Telegram Bot

Телеграм-бот, который:
1. Сканирует рынки Polymarket через Gamma API.
2. Отбирает недооцененные low-liquidity лоты.
3. Генерирует prompt для ChatGPT.
4. Принимает JSON-рекомендации, хранит историю сканов/ответов.
5. В ручном или auto режиме отправляет on-chain транзакции (локальная подпись через `web3.py` + `eth_account`).

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

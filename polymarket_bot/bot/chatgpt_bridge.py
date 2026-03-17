from __future__ import annotations

import json
from dataclasses import asdict
from textwrap import dedent

from .models import AiRecommendation, MarketCandidate


class ChatGPTBridge:
    """
    Генерация промпта и разбор ответа.
    По ТЗ промпт отправляется пользователю для вставки в ChatGPT.
    """

    def build_prompt(self, markets: list[MarketCandidate]) -> str:
        payload = [asdict(m) for m in markets]
        return dedent(
            f"""
            Ты quantitative-аналитик прогнозных рынков.
            Проанализируй рынки Polymarket и выбери лучшие ставки по двум стратегиям:
            1) value_edge
            2) high_probability

            ВАЖНО:
            - Используй current_yes_price как РЕАЛЬНУЮ рыночную цену покупки сейчас.
            - Не используй hypothetical/потенциальные цены.
            - Ставки только по событиям, где ends_at <= 14 дней.
            - stake_usd должен быть <= 10.

            Данные рынков JSON:
            {json.dumps(payload, ensure_ascii=False, indent=2)}

            Верни СТРОГО JSON-массив объектов вида:
            [
              {{
                "market_id": "...",
                "outcome": "YES|NO",
                "confidence": 0.0,
                "estimated_win_probability": 0.0,
                "expected_value": 0.0,
                "stake_usd": 0.0,
                "max_entry_price": 0.0,
                "reason": "короткое объяснение"
              }}
            ]
            Условия:
            - confidence от 0 до 1
            - estimated_win_probability от 0 до 1
            - expected_value > 0
            - stake_usd от 1 до 10
            - max_entry_price > 0 (реальная цена входа)
            """
        ).strip()

    def parse_recommendations(self, text: str) -> list[AiRecommendation]:
        raw = json.loads(text)
        recs: list[AiRecommendation] = []
        for item in raw:
            recs.append(
                AiRecommendation(
                    market_id=str(item["market_id"]),
                    outcome=str(item.get("outcome", "YES")),
                    confidence=float(item["confidence"]),
                    estimated_win_probability=float(item["estimated_win_probability"]),
                    expected_value=float(item["expected_value"]),
                    stake_usd=float(item["stake_usd"]),
                    max_entry_price=float(item["max_entry_price"]),
                    reason=str(item.get("reason", "")),
                )
            )
        return recs

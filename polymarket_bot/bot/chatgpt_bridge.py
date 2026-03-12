from __future__ import annotations

import json
from textwrap import dedent

from .models import AiRecommendation, MarketCandidate


class ChatGPTBridge:
    """
    Генерация промпта и разбор ответа.
    По ТЗ промпт отправляется пользователю для вставки в ChatGPT.
    """

    def build_prompt(self, markets: list[MarketCandidate]) -> str:
        payload = [m.__dict__ for m in markets]
        return dedent(
            f"""
            Ты quantitative-аналитик прогнозных рынков.
            Проанализируй список рынков Polymarket и выбери лучшие ставки.

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
                "reason": "короткое объяснение"
              }}
            ]
            Условия:
            - confidence от 0 до 1
            - estimated_win_probability от 0 до 1
            - expected_value > 0
            - stake_usd в разумном диапазоне
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
                    reason=str(item.get("reason", "")),
                )
            )
        return recs

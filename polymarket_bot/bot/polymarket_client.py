from __future__ import annotations

import httpx

from .models import MarketCandidate


class PolymarketClient:
    def __init__(self, gamma_url: str, timeout: float = 20.0) -> None:
        self.gamma_url = gamma_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def fetch_active_markets(self, limit: int = 200) -> list[dict]:
        # Endpoint Gamma API; можно заменить на Subgraph при необходимости.
        response = self.client.get(
            f"{self.gamma_url}/markets",
            params={"active": "true", "closed": "false", "limit": str(limit), "order": "volume24hr", "ascending": "false"},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        if isinstance(data, list):
            return data
        return []


class MarketScanner:
    def __init__(self, min_edge: float, max_liquidity_usd: float) -> None:
        self.min_edge = min_edge
        self.max_liquidity_usd = max_liquidity_usd

    @staticmethod
    def _extract_probability(market: dict) -> float:
        # lastTradePrice/noPrice/yesPrice форматы зависят от источника.
        for key in ("yesPrice", "probability", "lastTradePrice"):
            value = market.get(key)
            if value is not None:
                return float(value)
        return 0.5

    @staticmethod
    def _expected_probability(market: dict) -> float:
        # Простая эвристика: если объем высокий относительно ликвидности, вероятность недооценки чуть выше.
        liquidity = float(market.get("liquidity", 0) or 0)
        volume24 = float(market.get("volume24hr", 0) or 0)
        base = 0.5
        signal = min(0.2, volume24 / max(liquidity, 1.0) * 0.05)
        return min(0.95, max(0.05, base + signal))

    def select_candidates(self, raw_markets: list[dict], max_candidates: int, skip_market_ids: set[str]) -> list[MarketCandidate]:
        candidates: list[MarketCandidate] = []
        for m in raw_markets:
            market_id = str(m.get("id") or m.get("conditionId") or "")
            if not market_id or market_id in skip_market_ids:
                continue

            liquidity = float(m.get("liquidity", 0) or 0)
            if liquidity > self.max_liquidity_usd:
                continue

            p_market = self._extract_probability(m)
            p_expected = self._expected_probability(m)
            edge = p_expected - p_market
            if edge < self.min_edge:
                continue

            candidates.append(
                MarketCandidate(
                    market_id=market_id,
                    question=str(m.get("question", "Unknown market")),
                    outcome="YES",
                    market_url=str(m.get("url") or m.get("slug") or ""),
                    probability=p_market,
                    expected_probability=p_expected,
                    edge=edge,
                    liquidity_usd=liquidity,
                    volume_24h=float(m.get("volume24hr", 0) or 0),
                )
            )

        candidates.sort(key=lambda x: x.edge, reverse=True)
        return candidates[:max_candidates]

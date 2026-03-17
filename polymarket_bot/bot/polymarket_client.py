from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from .models import MarketCandidate


class PolymarketClient:
    def __init__(self, gamma_url: str, timeout: float = 20.0) -> None:
        self.gamma_url = gamma_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def fetch_active_markets(self, limit: int = 200, page_size: int = 500) -> list[dict]:
        """
        Загружает рынки батчами через offset, чтобы можно было забрать >500.
        """
        all_markets: list[dict] = []
        offset = 0
        while len(all_markets) < limit:
            current_limit = min(page_size, limit - len(all_markets))
            response = self.client.get(
                f"{self.gamma_url}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": str(current_limit),
                    "offset": str(offset),
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            response.raise_for_status()
            data = response.json()
            batch = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            if not batch:
                break
            all_markets.extend(batch)
            if len(batch) < current_limit:
                break
            offset += current_limit
        return all_markets


class MarketScanner:
    def __init__(
        self,
        min_edge_low_prob: float,
        min_edge_high_prob: float,
        max_event_horizon_days: int = 14,
        low_prob_threshold: float = 0.20,
        high_prob_threshold: float = 0.80,
    ) -> None:
        self.min_edge_low_prob = min_edge_low_prob
        self.min_edge_high_prob = min_edge_high_prob
        self.max_event_horizon_days = max_event_horizon_days
        self.low_prob_threshold = low_prob_threshold
        self.high_prob_threshold = high_prob_threshold

    @staticmethod
    def _extract_probability(market: dict) -> float:
        for key in ("yesPrice", "probability", "lastTradePrice"):
            value = market.get(key)
            if value is not None:
                return float(value)
        return 0.5

    @staticmethod
    def _expected_probability(market: dict) -> float:
        liquidity = float(market.get("liquidity", 0) or 0)
        volume24 = float(market.get("volume24hr", 0) or 0)
        base = 0.5
        signal = min(0.2, volume24 / max(liquidity, 1.0) * 0.05)
        return min(0.95, max(0.05, base + signal))

    @staticmethod
    def _parse_end_at(market: dict) -> datetime | None:
        raw = market.get("endDate") or market.get("endTime") or market.get("resolutionDate")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

    def _within_two_weeks(self, market: dict) -> tuple[bool, str]:
        end_at = self._parse_end_at(market)
        if not end_at:
            return False, ""
        now = datetime.now(timezone.utc)
        if end_at < now:
            return False, ""
        if end_at > now + timedelta(days=self.max_event_horizon_days):
            return False, ""
        return True, end_at.isoformat()

    def collect_filter_stats(self, raw_markets: list[dict], skip_market_ids: set[str]) -> dict[str, int]:
        stats = {
            "total_raw": len(raw_markets),
            "skipped_already_scanned": 0,
            "failed_horizon": 0,
            "failed_liquidity": 0,
            "failed_probability_bucket": 0,
            "failed_edge": 0,
            "passed_low_probability": 0,
            "passed_high_probability": 0,
            "passed_total": 0,
        }

        for m in raw_markets:
            market_id = str(m.get("id") or m.get("conditionId") or "")
            if not market_id or market_id in skip_market_ids:
                stats["skipped_already_scanned"] += 1
                continue

            in_window, _ = self._within_two_weeks(m)
            if not in_window:
                stats["failed_horizon"] += 1
                continue

            current_price = self._extract_probability(m)
            expected_probability = self._expected_probability(m)
            edge = expected_probability - current_price

            in_low_bucket = current_price <= self.low_prob_threshold
            in_high_bucket = current_price >= self.high_prob_threshold
            if not in_low_bucket and not in_high_bucket:
                stats["failed_probability_bucket"] += 1
                continue

            if in_low_bucket and edge >= self.min_edge_low_prob:
                stats["passed_low_probability"] += 1
                stats["passed_total"] += 1
                continue

            if in_high_bucket and edge >= self.min_edge_high_prob:
                stats["passed_high_probability"] += 1
                stats["passed_total"] += 1
                continue

            stats["failed_edge"] += 1

        return stats

    def select_candidates(self, raw_markets: list[dict], max_candidates: int, skip_market_ids: set[str]) -> list[MarketCandidate]:
        candidates: list[MarketCandidate] = []
        for m in raw_markets:
            market_id = str(m.get("id") or m.get("conditionId") or "")
            if not market_id or market_id in skip_market_ids:
                continue

            in_window, ends_at = self._within_two_weeks(m)
            if not in_window:
                continue

            current_price = self._extract_probability(m)
            expected_probability = self._expected_probability(m)
            edge = expected_probability - current_price
            liquidity = float(m.get("liquidity", 0) or 0)

            if current_price <= self.low_prob_threshold and edge >= self.min_edge_low_prob:
                candidates.append(
                    MarketCandidate(
                        market_id=market_id,
                        question=str(m.get("question", "Unknown market")),
                        outcome="YES",
                        market_url=str(m.get("url") or m.get("slug") or ""),
                        probability=current_price,
                        expected_probability=expected_probability,
                        edge=edge,
                        liquidity_usd=liquidity,
                        volume_24h=float(m.get("volume24hr", 0) or 0),
                        ends_at=ends_at,
                        strategy="low_probability",
                        current_yes_price=current_price,
                    )
                )
                continue

            if current_price >= self.high_prob_threshold and edge >= self.min_edge_high_prob:
                candidates.append(
                    MarketCandidate(
                        market_id=market_id,
                        question=str(m.get("question", "Unknown market")),
                        outcome="YES",
                        market_url=str(m.get("url") or m.get("slug") or ""),
                        probability=current_price,
                        expected_probability=expected_probability,
                        edge=edge,
                        liquidity_usd=liquidity,
                        volume_24h=float(m.get("volume24hr", 0) or 0),
                        ends_at=ends_at,
                        strategy="high_probability",
                        current_yes_price=current_price,
                    )
                )

        candidates.sort(key=lambda x: (x.edge, x.expected_probability), reverse=True)
        return candidates[:max_candidates]

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarketCandidate:
    market_id: str
    question: str
    outcome: str
    market_url: str
    probability: float
    expected_probability: float
    edge: float
    liquidity_usd: float
    volume_24h: float


@dataclass(slots=True)
class ScanBatch:
    id: str
    created_at: datetime
    markets: list[MarketCandidate]


@dataclass(slots=True)
class AiRecommendation:
    market_id: str
    outcome: str
    confidence: float
    estimated_win_probability: float
    expected_value: float
    stake_usd: float
    reason: str


@dataclass(slots=True)
class TradeResult:
    market_id: str
    tx_hash: str
    status: str
    sent_amount_usd: float

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import AiRecommendation, MarketCandidate


class BotStorage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scan_markets (
                scan_id TEXT NOT NULL,
                market_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(scan_id, market_id)
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                scan_id TEXT NOT NULL,
                market_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(scan_id, market_id)
            );

            CREATE TABLE IF NOT EXISTS trades (
                market_id TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def save_scan(self, scan_id: str, prompt: str, markets: list[MarketCandidate]) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO scans(id, created_at, prompt, status) VALUES(?, ?, ?, ?)",
            (scan_id, now, prompt, "pending_ai"),
        )
        for m in markets:
            self.conn.execute(
                "INSERT OR REPLACE INTO scan_markets(scan_id, market_id, payload) VALUES(?, ?, ?)",
                (scan_id, m.market_id, json.dumps(asdict(m), ensure_ascii=False)),
            )
        self.conn.commit()

    def mark_scan_reviewed(self, scan_id: str) -> None:
        self.conn.execute("UPDATE scans SET status = ? WHERE id = ?", ("reviewed", scan_id))
        self.conn.commit()

    def save_recommendations(self, scan_id: str, recs: list[AiRecommendation]) -> None:
        for rec in recs:
            self.conn.execute(
                "INSERT OR REPLACE INTO recommendations(scan_id, market_id, payload) VALUES(?, ?, ?)",
                (scan_id, rec.market_id, json.dumps(asdict(rec), ensure_ascii=False)),
            )
        self.conn.commit()

    def save_trade(self, market_id: str, tx_hash: str, payload: dict) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO trades(market_id, tx_hash, created_at, payload) VALUES(?, ?, ?, ?)",
            (market_id, tx_hash, now, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def already_scanned_market_ids(self) -> set[str]:
        rows = self.conn.execute("SELECT market_id FROM scan_markets").fetchall()
        return {r["market_id"] for r in rows}

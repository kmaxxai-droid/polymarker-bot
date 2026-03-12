from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: int
    polygon_rpc_url: str
    wallet_private_key: str
    wallet_address: str
    chain_id: int
    polymarket_gamma_url: str
    max_candidates: int
    max_liquidity_usd: float
    min_edge: float
    bet_min_usd: float
    bet_max_usd: float
    max_slippage_bps: int
    auto_mode: bool
    sqlite_path: Path
    bet_executor_contract: str
    bet_executor_abi_path: Path



def _must(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Environment variable {name} is required")
    return value


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        telegram_bot_token=_must("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=int(_must("TELEGRAM_CHAT_ID")),
        polygon_rpc_url=_must("POLYGON_RPC_URL"),
        wallet_private_key=_must("WALLET_PRIVATE_KEY"),
        wallet_address=_must("WALLET_ADDRESS"),
        chain_id=int(os.getenv("CHAIN_ID", "137")),
        polymarket_gamma_url=os.getenv("POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com"),
        max_candidates=int(os.getenv("MAX_CANDIDATES", "30")),
        max_liquidity_usd=float(os.getenv("MAX_LIQUIDITY_USD", "1000")),
        min_edge=float(os.getenv("MIN_EDGE", "0.03")),
        bet_min_usd=float(os.getenv("BET_MIN_USD", "5")),
        bet_max_usd=float(os.getenv("BET_MAX_USD", "25")),
        max_slippage_bps=int(os.getenv("MAX_SLIPPAGE_BPS", "150")),
        auto_mode=os.getenv("AUTO_MODE", "false").lower() == "true",
        sqlite_path=Path(os.getenv("SQLITE_PATH", "data/polymarket_bot.db")),
        bet_executor_contract=os.getenv("BET_EXECUTOR_CONTRACT", "0x0000000000000000000000000000000000000000"),
        bet_executor_abi_path=Path(os.getenv("BET_EXECUTOR_ABI_PATH", "abi/bet_executor.json")),
    )

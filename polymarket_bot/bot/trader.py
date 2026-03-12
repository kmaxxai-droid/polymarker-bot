from __future__ import annotations

import json
from pathlib import Path

from eth_account import Account
from web3 import Web3

from .config import Settings
from .models import AiRecommendation, TradeResult


class PolymarketTrader:
    """
    Модуль отправки on-chain транзакции c локальной подписью.
    В production подключите ABI/адрес контракта-исполнителя для реального исполнения ордера Polymarket.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
        self.account = Account.from_key(settings.wallet_private_key)

        if settings.bet_executor_abi_path.exists():
            abi = json.loads(Path(settings.bet_executor_abi_path).read_text(encoding="utf-8"))
            self.executor_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(settings.bet_executor_contract),
                abi=abi,
            )
        else:
            self.executor_contract = None

    def _check_slippage(self, market_price: float, max_price: float) -> None:
        slippage = (max_price - market_price) / max(market_price, 1e-9)
        max_slippage = self.settings.max_slippage_bps / 10_000
        if slippage > max_slippage:
            raise ValueError(f"Slippage too high: {slippage:.4f} > {max_slippage:.4f}")

    def place_bet(self, recommendation: AiRecommendation, market_price: float) -> TradeResult:
        # Ограничиваем размер ставки по risk-policy.
        amount = max(self.settings.bet_min_usd, min(recommendation.stake_usd, self.settings.bet_max_usd))
        max_price = recommendation.estimated_win_probability
        self._check_slippage(market_price, max_price)

        if not self.executor_contract:
            # Fallback dry-run: показывает, что прошло все проверки. Для реального продакшена задайте ABI и контракт.
            return TradeResult(
                market_id=recommendation.market_id,
                tx_hash="dry_run_no_executor_contract",
                status="simulated",
                sent_amount_usd=amount,
            )

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.executor_contract.functions.placeBet(
            recommendation.market_id,
            recommendation.outcome,
            int(amount * 1_000_000),  # USDC 6 decimals
            int(max_price * 10_000),
        ).build_transaction(
            {
                "from": self.account.address,
                "chainId": self.settings.chain_id,
                "nonce": nonce,
                "gas": 350_000,
                "maxFeePerGas": self.w3.to_wei("80", "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei("35", "gwei"),
            }
        )

        signed = self.w3.eth.account.sign_transaction(tx, private_key=self.settings.wallet_private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return TradeResult(
            market_id=recommendation.market_id,
            tx_hash=tx_hash.hex(),
            status="submitted",
            sent_amount_usd=amount,
        )

"""
Wallet Service - TradingBot Backend

Denna modul hanterar plånboksinformation från Bitfinex API.
Inkluderar funktioner för att hämta plånbokssaldon och hantera plånbokstransaktioner.
"""

from typing import List, Optional

import httpx
from pydantic import BaseModel

from config.settings import Settings
from rest.auth import build_auth_headers
from utils.logger import get_logger

logger = get_logger(__name__)


class WalletBalance(BaseModel):
    """Modell för plånbokssaldo."""

    wallet_type: str  # "exchange", "margin", "funding"
    currency: str
    balance: float
    unsettled_interest: float = 0.0
    available_balance: Optional[float] = None

    @classmethod
    def from_bitfinex_data(cls, data: List) -> "WalletBalance":
        """Skapar en WalletBalance från Bitfinex API-data."""
        if len(data) < 4:
            raise ValueError(f"Ogiltig plånboksdata: {data}")

        return cls(
            wallet_type=data[0],
            currency=data[1],
            balance=float(data[2]),
            unsettled_interest=float(data[3]) if len(data) > 3 else 0.0,
            available_balance=float(data[4]) if len(data) > 4 else None,
        )


class WalletService:
    """Service för att hämta och hantera plånboksinformation från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.base_url = getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL

    async def get_wallets(self) -> List[WalletBalance]:
        """
        Hämtar alla plånböcker från Bitfinex.

        Returns:
            Lista med WalletBalance-objekt
        """
        try:
            endpoint = "auth/r/wallets"
            headers = build_auth_headers(endpoint)

            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar plånböcker från {self.base_url}/{endpoint}")
                response = await client.post(f"{self.base_url}/{endpoint}", headers=headers)
                response.raise_for_status()

                wallets_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(wallets_data)} plånböcker")

                wallets = [WalletBalance.from_bitfinex_data(wallet) for wallet in wallets_data]
                return wallets

        except Exception as e:
            logger.error(f"Fel vid hämtning av plånböcker: {e}")
            raise

    async def get_wallet_by_type_and_currency(self, wallet_type: str, currency: str) -> Optional[WalletBalance]:
        """
        Hämtar en specifik plånbok baserat på typ och valuta.

        Args:
            wallet_type: Plånbokstyp ("exchange", "margin", "funding")
            currency: Valutakod (t.ex. "BTC", "USD")

        Returns:
            WalletBalance-objekt eller None om plånboken inte hittas
        """
        wallets = await self.get_wallets()

        for wallet in wallets:
            if wallet.wallet_type.lower() == wallet_type.lower() and wallet.currency.lower() == currency.lower():
                return wallet

        return None

    async def get_exchange_wallets(self) -> List[WalletBalance]:
        """
        Hämtar alla exchange-plånböcker.

        Returns:
            Lista med WalletBalance-objekt för exchange-plånböcker
        """
        wallets = await self.get_wallets()
        return [wallet for wallet in wallets if wallet.wallet_type.lower() == "exchange"]

    async def get_margin_wallets(self) -> List[WalletBalance]:
        """
        Hämtar alla margin-plånböcker.

        Returns:
            Lista med WalletBalance-objekt för margin-plånböcker
        """
        wallets = await self.get_wallets()
        return [wallet for wallet in wallets if wallet.wallet_type.lower() == "margin"]

    async def get_funding_wallets(self) -> List[WalletBalance]:
        """
        Hämtar alla funding-plånböcker.

        Returns:
            Lista med WalletBalance-objekt för funding-plånböcker
        """
        wallets = await self.get_wallets()
        return [wallet for wallet in wallets if wallet.wallet_type.lower() == "funding"]

    async def get_total_balance_usd(self) -> float:
        """
        Beräknar det totala saldot i USD över alla plånböcker.
        Detta är en förenklad implementation som antar att USD-plånböcker har direkt USD-värde
        och att andra valutor skulle behöva konverteras (inte implementerat här).

        Returns:
            Totalt saldo i USD
        """
        wallets = await self.get_wallets()
        usd_wallets = [wallet for wallet in wallets if wallet.currency.upper() == "USD"]

        total_usd = sum(wallet.balance for wallet in usd_wallets)
        return total_usd


# Skapa en global instans av WalletService
wallet_service = WalletService()


# Exportera funktioner för enkel användning
async def get_wallets() -> List[WalletBalance]:
    return await wallet_service.get_wallets()


async def get_wallet_by_type_and_currency(wallet_type: str, currency: str) -> Optional[WalletBalance]:
    return await wallet_service.get_wallet_by_type_and_currency(wallet_type, currency)


async def get_exchange_wallets() -> List[WalletBalance]:
    return await wallet_service.get_exchange_wallets()


async def get_margin_wallets() -> List[WalletBalance]:
    return await wallet_service.get_margin_wallets()


async def get_funding_wallets() -> List[WalletBalance]:
    return await wallet_service.get_funding_wallets()


async def get_total_balance_usd() -> float:
    return await wallet_service.get_total_balance_usd()

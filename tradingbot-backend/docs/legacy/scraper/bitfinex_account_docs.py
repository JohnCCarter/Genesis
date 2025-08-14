"""
Bitfinex Account API Documentation Scraper

Denna modul hämtar och strukturerar information om konto-relaterade endpoints
från Bitfinex API-dokumentation (wallet, positions, margin).
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bitfinex_account_scraper")

# Konstanter
CACHE_DIR = Path(__file__).parent.parent / "cache" / "bitfinex_docs"
CACHE_VALIDITY_DAYS = 7  # Hur länge cache är giltig innan uppdatering
# Huvudsidan för autentiserade endpoints
REST_AUTH_URL = "https://docs.bitfinex.com/docs/rest-auth"

# Specifika URL:er för detaljerad dokumentation (v2 API)
WALLETS_URL = "https://docs.bitfinex.com/reference/rest-auth-wallets"
POSITIONS_URL = "https://docs.bitfinex.com/reference/rest-auth-positions"
# För margin info använder vi v1 API dokumentation eftersom v2 inte verkar ha en specifik sida för detta
MARGIN_URL = "https://docs.bitfinex.com/v1/reference/rest-auth-margin-information"


class BitfinexAccountScraper:
    """
    Klass för att skrapa och strukturera Bitfinex API-dokumentation
    relaterad till konto-funktioner (wallet, positions, margin).
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_validity_days: int = CACHE_VALIDITY_DAYS,
    ):
        """
        Initialiserar scrapern.

        Args:
            cache_dir: Katalog för cachad data
            cache_validity_days: Antal dagar som cachad data är giltig
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_validity_days = cache_validity_days
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 Genesis-Trading-Bot Account Documentation Helper"}
        )

        # Skapa cache-katalog om den inte finns
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initiera data-strukturer
        self.wallet_info: Dict[str, Any] = {}
        self.positions_info: Dict[str, Any] = {}
        self.margin_info: Dict[str, Any] = {}

    def _get_cached_or_fetch(self, url: str, section: str) -> dict:
        """
        Hämtar data från cache eller från webben om cachen är för gammal.

        Args:
            url: URL att hämta
            section: Sektion för cachelagring

        Returns:
            Dict med hämtad data
        """
        cache_file = self.cache_dir / f"{section}_account.json"

        # Kontrollera om cachen finns och är giltig
        if cache_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if file_age < timedelta(days=self.cache_validity_days):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        logger.info(f"Använder cachad data för {section}_account")
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Fel vid läsning av cache: {e}")

        # Hämta från webben
        logger.info(f"Hämtar {section}_account från {url}")
        try:
            # Använd en mer webbläsarliknande User-Agent för att undvika 404
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            response = self.session.get(url, headers=headers)
            response.raise_for_status()

            # Spara till cache
            with open(cache_file, "w", encoding="utf-8") as f:
                html_content = response.text
                json.dump({"html": html_content}, f, ensure_ascii=False, indent=2)

            # Vänta lite för att inte överbelasta servern
            time.sleep(0.5)

            return {"html": html_content}

        except requests.RequestException as e:
            logger.error(f"Fel vid hämtning av {url}: {e}")

            # Försök använda cachen även om den är gammal
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        logger.warning(
                            f"Använder gammal cache för {section}_account på grund av nätverksfel"
                        )
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            # Returnera tom data om inget annat fungerar
            return {}

    def _parse_wallet_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyserar HTML-innehåll för wallet-dokumentation.

        Args:
            html_content: HTML-innehåll att analysera

        Returns:
            Strukturerad data om wallet-endpoints
        """
        soup = BeautifulSoup(html_content, "html.parser")
        result = {
            "section": "wallet",
            "endpoint": "auth/r/wallets",
            "method": "POST",
            "description": "Hämtar information om alla plånböcker",
            "response_fields": [],
            "examples": [],
        }

        # Försök hitta beskrivning
        description_section = soup.find(
            string=re.compile("Retrieve your wallet balances", re.IGNORECASE)
        )
        if description_section and description_section.parent:
            result["description"] = description_section.get_text(strip=True)

        # Hitta svarsfält från tabeller
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

            # Kontrollera om detta är en tabell med fältbeskrivningar
            if "field" in headers and "description" in headers:
                for row in table.find_all("tr")[1:]:  # Skippa header-raden
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        field = {
                            "name": cells[0].get_text(strip=True),
                            "description": cells[1].get_text(strip=True),
                        }
                        if len(cells) > 2:
                            field["type"] = cells[2].get_text(strip=True)

                        result["response_fields"].append(field)

        # Hitta kodexempel
        code_blocks = soup.find_all("pre")
        for block in code_blocks:
            code_text = block.get_text(strip=True)
            if "wallets" in code_text.lower() or "wallet" in code_text.lower():
                lang = "unknown"
                if block.parent and block.parent.get("class"):
                    parent_classes = block.parent.get("class")
                    for lang_class in [
                        "language-javascript",
                        "language-python",
                        "language-shell",
                    ]:
                        if lang_class in parent_classes:
                            lang = lang_class.split("-")[1]
                            break

                result["examples"].append({"language": lang, "code": code_text})

        return result

    def _parse_positions_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyserar HTML-innehåll för positions-dokumentation.

        Args:
            html_content: HTML-innehåll att analysera

        Returns:
            Strukturerad data om positions-endpoints
        """
        soup = BeautifulSoup(html_content, "html.parser")
        result = {
            "section": "positions",
            "endpoint": "auth/r/positions",
            "method": "POST",
            "description": "Hämtar information om alla aktiva positioner",
            "response_fields": [],
            "examples": [],
        }

        # Försök hitta beskrivning
        description_section = soup.find(string=re.compile("Get positions", re.IGNORECASE))
        if description_section and description_section.parent:
            result["description"] = description_section.get_text(strip=True)

        # Hitta svarsfält från tabeller
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

            # Kontrollera om detta är en tabell med fältbeskrivningar
            if "field" in headers and "description" in headers:
                for row in table.find_all("tr")[1:]:  # Skippa header-raden
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        field = {
                            "name": cells[0].get_text(strip=True),
                            "description": cells[1].get_text(strip=True),
                        }
                        if len(cells) > 2:
                            field["type"] = cells[2].get_text(strip=True)

                        result["response_fields"].append(field)

        # Hitta kodexempel
        code_blocks = soup.find_all("pre")
        for block in code_blocks:
            code_text = block.get_text(strip=True)
            if "positions" in code_text.lower() or "position" in code_text.lower():
                lang = "unknown"
                if block.parent and block.parent.get("class"):
                    parent_classes = block.parent.get("class")
                    for lang_class in [
                        "language-javascript",
                        "language-python",
                        "language-shell",
                    ]:
                        if lang_class in parent_classes:
                            lang = lang_class.split("-")[1]
                            break

                result["examples"].append({"language": lang, "code": code_text})

        return result

    def _parse_margin_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyserar HTML-innehåll för margin-dokumentation.

        Args:
            html_content: HTML-innehåll att analysera

        Returns:
            Strukturerad data om margin-endpoints
        """
        soup = BeautifulSoup(html_content, "html.parser")
        result = {
            "section": "margin",
            "endpoint": "auth/r/info/margin",
            "method": "POST",
            "description": "Hämtar margin-information",
            "response_fields": [],
            "examples": [],
        }

        # Försök hitta beskrivning
        description_section = soup.find(string=re.compile("Get account margin info", re.IGNORECASE))
        if description_section and description_section.parent:
            result["description"] = description_section.get_text(strip=True)

        # Hitta svarsfält från tabeller
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

            # Kontrollera om detta är en tabell med fältbeskrivningar
            if "field" in headers and "description" in headers:
                for row in table.find_all("tr")[1:]:  # Skippa header-raden
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        field = {
                            "name": cells[0].get_text(strip=True),
                            "description": cells[1].get_text(strip=True),
                        }
                        if len(cells) > 2:
                            field["type"] = cells[2].get_text(strip=True)

                        result["response_fields"].append(field)

        # Hitta kodexempel
        code_blocks = soup.find_all("pre")
        for block in code_blocks:
            code_text = block.get_text(strip=True)
            if "margin" in code_text.lower():
                lang = "unknown"
                if block.parent and block.parent.get("class"):
                    parent_classes = block.parent.get("class")
                    for lang_class in [
                        "language-javascript",
                        "language-python",
                        "language-shell",
                    ]:
                        if lang_class in parent_classes:
                            lang = lang_class.split("-")[1]
                            break

                result["examples"].append({"language": lang, "code": code_text})

        return result

    def fetch_wallet_info(self) -> Dict[str, Any]:
        """
        Hämtar information om wallet-endpoints.

        Returns:
            Dict med information om wallet-endpoints
        """
        data = self._get_cached_or_fetch(WALLETS_URL, "wallet")

        if "html" in data:
            self.wallet_info = self._parse_wallet_html(data["html"])
        else:
            # Fallback om vi inte kan skrapa dokumentationen
            self.wallet_info = {
                "section": "wallet",
                "endpoint": "auth/r/wallets",
                "method": "POST",
                "description": "Hämtar information om alla plånböcker",
                "response_fields": [
                    {
                        "name": "WALLET_TYPE",
                        "description": "Typ av plånbok (exchange, margin, funding)",
                    },
                    {"name": "CURRENCY", "description": "Valutakod"},
                    {"name": "BALANCE", "description": "Tillgängligt saldo"},
                    {"name": "UNSETTLED_INTEREST", "description": "Oavgjort ränta"},
                    {
                        "name": "AVAILABLE_BALANCE",
                        "description": "Tillgängligt saldo för handel",
                    },
                ],
                "examples": [],
            }

        return self.wallet_info

    def fetch_positions_info(self) -> Dict[str, Any]:
        """
        Hämtar information om positions-endpoints.

        Returns:
            Dict med information om positions-endpoints
        """
        data = self._get_cached_or_fetch(POSITIONS_URL, "positions")

        if "html" in data:
            self.positions_info = self._parse_positions_html(data["html"])
        else:
            # Fallback om vi inte kan skrapa dokumentationen
            self.positions_info = {
                "section": "positions",
                "endpoint": "auth/r/positions",
                "method": "POST",
                "description": "Hämtar information om alla aktiva positioner",
                "response_fields": [
                    {"name": "SYMBOL", "description": "Handelssymbol (t.ex. tBTCUSD)"},
                    {
                        "name": "STATUS",
                        "description": "Status för positionen (ACTIVE, CLOSED)",
                    },
                    {
                        "name": "AMOUNT",
                        "description": "Mängd (positiv för long, negativ för short)",
                    },
                    {
                        "name": "BASE_PRICE",
                        "description": "Genomsnittligt pris för positionen",
                    },
                    {
                        "name": "FUNDING",
                        "description": "Finansiering som används för positionen",
                    },
                    {
                        "name": "FUNDING_TYPE",
                        "description": "Typ av finansiering (0 för daily, 1 för term)",
                    },
                ],
                "examples": [],
            }

        return self.positions_info

    def fetch_margin_info(self) -> Dict[str, Any]:
        """
        Hämtar information om margin-endpoints.

        Returns:
            Dict med information om margin-endpoints
        """
        data = self._get_cached_or_fetch(MARGIN_URL, "margin")

        if "html" in data:
            self.margin_info = self._parse_margin_html(data["html"])
        else:
            # Fallback om vi inte kan skrapa dokumentationen
            self.margin_info = {
                "section": "margin",
                "endpoint": "auth/r/info/margin",
                "method": "POST",
                "description": "Hämtar margin-information",
                "response_fields": [
                    {"name": "MARGIN_BALANCE", "description": "Margin-saldo"},
                    {
                        "name": "UNREALIZED_PL",
                        "description": "Orealiserad vinst/förlust",
                    },
                    {"name": "UNREALIZED_SWAP", "description": "Orealiserad swap"},
                    {"name": "NET_VALUE", "description": "Nettovärde"},
                    {"name": "REQUIRED_MARGIN", "description": "Krävd margin"},
                ],
                "examples": [],
            }

        return self.margin_info

    def fetch_all_account_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Hämtar all konto-relaterad information.

        Returns:
            Dict med all konto-relaterad information
        """
        wallet_info = self.fetch_wallet_info()
        positions_info = self.fetch_positions_info()
        margin_info = self.fetch_margin_info()

        return {
            "wallet": wallet_info,
            "positions": positions_info,
            "margin": margin_info,
        }

    def generate_account_code_examples(self) -> Dict[str, Dict[str, str]]:
        """
        Genererar kodexempel för konto-relaterade endpoints.

        Returns:
            Dict med kodexempel för wallet, positions och margin
        """
        examples = {
            "wallet": {"python": self._generate_wallet_example()},
            "positions": {"python": self._generate_positions_example()},
            "margin": {"python": self._generate_margin_example()},
        }

        return examples

    def _generate_wallet_example(self) -> str:
        """
        Genererar Python-exempel för wallet-endpoint.

        Returns:
            Python-kodexempel för wallet-endpoint
        """
        return """
async def get_wallets():
    \"\"\"
    Hämtar alla plånböcker från Bitfinex.
    
    Returns:
        Lista med plånboksinformation
    \"\"\"
    try:
        endpoint = "auth/r/wallets"
        headers = build_auth_headers(endpoint)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            
            wallets_data = response.json()
            
            # Formatera svaret
            wallets = []
            for wallet in wallets_data:
                wallets.append({
                    "wallet_type": wallet[0],  # "exchange", "margin", "funding"
                    "currency": wallet[1],
                    "balance": float(wallet[2]),
                    "unsettled_interest": float(wallet[3]) if len(wallet) > 3 else 0.0,
                    "available_balance": float(wallet[4]) if len(wallet) > 4 else None
                })
                
            return wallets
            
    except Exception as e:
        logger.error(f"Fel vid hämtning av plånböcker: {e}")
        raise
"""

    def _generate_positions_example(self) -> str:
        """
        Genererar Python-exempel för positions-endpoint.

        Returns:
            Python-kodexempel för positions-endpoint
        """
        return """
async def get_positions():
    \"\"\"
    Hämtar alla aktiva positioner från Bitfinex.
    
    Returns:
        Lista med positionsinformation
    \"\"\"
    try:
        endpoint = "auth/r/positions"
        headers = build_auth_headers(endpoint)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            
            positions_data = response.json()
            
            # Formatera svaret
            positions = []
            for position in positions_data:
                positions.append({
                    "symbol": position[0],
                    "status": position[1],
                    "amount": float(position[2]),
                    "base_price": float(position[3]),
                    "funding": float(position[4]) if len(position) > 4 else 0.0,
                    "funding_type": int(position[5]) if len(position) > 5 else 0
                })
                
            return positions
            
    except Exception as e:
        logger.error(f"Fel vid hämtning av positioner: {e}")
        raise
"""

    def _generate_margin_example(self) -> str:
        """
        Genererar Python-exempel för margin-endpoint.

        Returns:
            Python-kodexempel för margin-endpoint
        """
        return """
async def get_margin_info():
    \"\"\"
    Hämtar margin-information från Bitfinex.
    
    Returns:
        Dict med margin-information
    \"\"\"
    try:
        endpoint = "auth/r/info/margin"
        headers = build_auth_headers(endpoint)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            
            margin_data = response.json()
            
            # Formatera svaret
            margin_info = {
                "margin_balance": float(margin_data[0]),
                "unrealized_pl": float(margin_data[1]),
                "unrealized_swap": float(margin_data[2]),
                "net_value": float(margin_data[3]),
                "required_margin": float(margin_data[4]),
                "leverage": float(margin_data[3]) / float(margin_data[0]) if float(margin_data[0]) > 0 else 1.0
            }
                
            return margin_info
            
    except Exception as e:
        logger.error(f"Fel vid hämtning av margin-information: {e}")
        raise
"""


def main():
    """
    Huvudfunktion för att demonstrera användning av BitfinexAccountScraper.
    """
    scraper = BitfinexAccountScraper()

    # Hämta all konto-relaterad information
    logger.info("Hämtar Bitfinex konto-relaterad API-dokumentation...")
    account_info = scraper.fetch_all_account_info()

    # Visa information om wallet-endpoint
    logger.info(f"Wallet endpoint: {account_info['wallet']['endpoint']}")
    logger.info(f"Beskrivning: {account_info['wallet']['description']}")
    logger.info(f"Svarsfält: {len(account_info['wallet']['response_fields'])} fält")

    # Visa information om positions-endpoint
    logger.info(f"Positions endpoint: {account_info['positions']['endpoint']}")
    logger.info(f"Beskrivning: {account_info['positions']['description']}")
    logger.info(f"Svarsfält: {len(account_info['positions']['response_fields'])} fält")

    # Visa information om margin-endpoint
    logger.info(f"Margin endpoint: {account_info['margin']['endpoint']}")
    logger.info(f"Beskrivning: {account_info['margin']['description']}")
    logger.info(f"Svarsfält: {len(account_info['margin']['response_fields'])} fält")

    # Generera kodexempel
    examples = scraper.generate_account_code_examples()
    logger.info("Genererade kodexempel för wallet, positions och margin endpoints")

    logger.info("Skrapning av konto-relaterad dokumentation slutförd.")


if __name__ == "__main__":
    main()

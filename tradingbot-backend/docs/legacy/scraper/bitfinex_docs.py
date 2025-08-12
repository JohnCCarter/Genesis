"""
Bitfinex API Documentation Scraper

Denna modul hämtar och extraherar information från Bitfinex API-dokumentation.
Modulen hjälper till att hålla projektet uppdaterat med senaste API-ändringar,
samt tillhandahåller strukturerad information om endpoints, parametrar, felkoder, etc.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bitfinex_docs_scraper")

# Konstanter
CACHE_DIR = Path(__file__).parent.parent / "cache" / "bitfinex_docs"
CACHE_VALIDITY_DAYS = 7  # Hur länge cache är giltig innan uppdatering
BASE_URL = "https://docs.bitfinex.com/docs"
API_SECTIONS = ["rest-auth", "rest-public", "ws-auth", "ws-public"]


class BitfinexDocsScraper:
    """
    Klass för att skrapa och strukturera Bitfinex API-dokumentation.
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
            {"User-Agent": "Mozilla/5.0 Genesis-Trading-Bot Documentation Helper"}
        )

        # Skapa cache-katalog om den inte finns
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initiera data-strukturer
        self.endpoints: Dict[str, Dict] = {}
        self.error_codes: Dict[str, Dict] = {}
        self.symbols: List[Dict] = []
        self.order_types: Dict[str, Dict] = {}

    def _get_cached_or_fetch(self, url: str, section: str) -> dict:
        """
        Hämtar data från cache eller från webben om cachen är för gammal.

        Args:
            url: URL att hämta
            section: Sektion för cachelagring

        Returns:
            Dict med hämtad data
        """
        cache_file = self.cache_dir / f"{section}.json"

        # Kontrollera om cachen finns och är giltig
        if cache_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(
                cache_file.stat().st_mtime
            )
            if file_age < timedelta(days=self.cache_validity_days):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        logger.info(f"Använder cachad data för {section}")
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Fel vid läsning av cache: {e}")

        # Hämta från webben
        logger.info(f"Hämtar {section} från {url}")
        try:
            response = self.session.get(url)
            response.raise_for_status()

            # Spara till cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    (
                        response.json()
                        if "application/json"
                        in response.headers.get("Content-Type", "")
                        else {"html": response.text}
                    ),
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            # Vänta lite för att inte överbelasta servern
            time.sleep(0.5)

            return (
                response.json()
                if "application/json" in response.headers.get("Content-Type", "")
                else {"html": response.text}
            )

        except requests.RequestException as e:
            logger.error(f"Fel vid hämtning av {url}: {e}")

            # Försök använda cachen även om den är gammal
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        logger.warning(
                            f"Använder gammal cache för {section} på grund av nätverksfel"
                        )
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            # Returnera tom data om inget annat fungerar
            return {}

    def _parse_html_content(self, html_content: str, section: str) -> Dict[str, Any]:
        """
        Analyserar HTML-innehåll för att extrahera relevant information.

        Args:
            html_content: HTML-innehåll att analysera
            section: API-sektion som analyseras

        Returns:
            Strukturerad data från HTML
        """
        soup = BeautifulSoup(html_content, "html.parser")
        result = {"endpoints": [], "section": section}

        # Exempel: Extrahera endpoints från dokumentationen
        # Detta behöver anpassas baserat på dokumentationens struktur
        endpoint_elements = soup.select(".endpoint-item")  # Anpassa selektorn

        for elem in endpoint_elements:
            try:
                title_elem = elem.select_one(".endpoint-title")
                path_elem = elem.select_one(".endpoint-path")

                if title_elem and path_elem:
                    endpoint = {
                        "title": title_elem.get_text(strip=True),
                        "path": path_elem.get_text(strip=True),
                        "method": elem.get("data-method", "").upper(),
                        "description": (
                            elem.select_one(".endpoint-desc").get_text(strip=True)
                            if elem.select_one(".endpoint-desc")
                            else ""
                        ),
                        "parameters": [],
                    }

                    # Extrahera parametrar
                    param_table = elem.select_one(".params-table")
                    if param_table:
                        rows = param_table.select("tr")[1:]  # Skippa header
                        for row in rows:
                            cells = row.select("td")
                            if len(cells) >= 3:
                                param = {
                                    "name": cells[0].get_text(strip=True),
                                    "type": cells[1].get_text(strip=True),
                                    "required": "required"
                                    in cells[2].get_text(strip=True).lower(),
                                    "description": (
                                        cells[3].get_text(strip=True)
                                        if len(cells) > 3
                                        else ""
                                    ),
                                }
                                endpoint["parameters"].append(param)

                    result["endpoints"].append(endpoint)
            except Exception as e:
                logger.error(f"Fel vid parsing av endpoint: {e}")

        return result

    def fetch_all_documentation(self) -> None:
        """
        Hämtar all dokumentation från Bitfinex API.
        """
        for section in API_SECTIONS:
            url = f"{BASE_URL}/{section}"
            data = self._get_cached_or_fetch(url, section)

            if "html" in data:
                parsed_data = self._parse_html_content(data["html"], section)
                # Lagra strukturerad data
                for endpoint in parsed_data.get("endpoints", []):
                    key = f"{section}:{endpoint['path']}"
                    self.endpoints[key] = endpoint
            else:
                # Om API returnerar JSON direkt
                for item in data.get("items", []):
                    key = f"{section}:{item.get('path', '')}"
                    self.endpoints[key] = item

    def fetch_error_codes(self) -> Dict[str, Dict]:
        """
        Hämtar felkoder från Bitfinex API.

        Returns:
            Dict med felkoder och beskrivningar
        """
        url = "https://docs.bitfinex.com/docs/abbreviation-glossary"
        data = self._get_cached_or_fetch(url, "error_codes")

        if "html" in data:
            # Parsea HTML för att extrahera felkoder
            soup = BeautifulSoup(data["html"], "html.parser")
            error_table = soup.select_one(".error-codes-table")  # Anpassa selektorn

            if error_table:
                rows = error_table.select("tr")[1:]  # Skippa header
                for row in rows:
                    cells = row.select("td")
                    if len(cells) >= 2:
                        code = cells[0].get_text(strip=True)
                        self.error_codes[code] = {
                            "code": code,
                            "message": cells[1].get_text(strip=True),
                            "description": (
                                cells[2].get_text(strip=True) if len(cells) > 2 else ""
                            ),
                        }

        return self.error_codes

    def fetch_symbols(self) -> List[Dict]:
        """
        Hämtar tillgängliga handelspar från Bitfinex API.

        Returns:
            Lista med symboler och deras metadata
        """
        url = "https://api-pub.bitfinex.com/v2/conf/pub:list:pair:exchange"
        data = self._get_cached_or_fetch(url, "symbols")

        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            self.symbols = [{"symbol": f"t{s}"} for s in data[0]]

        # Hämta även testnet-symboler
        self.symbols.extend(
            [
                {"symbol": "tTESTBTC:TESTUSD", "is_paper": True},
                {"symbol": "tTESTETH:TESTUSD", "is_paper": True},
            ]
        )

        return self.symbols

    def fetch_order_types(self) -> Dict[str, Dict]:
        """
        Hämtar information om ordertyper.

        Returns:
            Dict med ordertyper och deras beskrivningar
        """
        url = "https://docs.bitfinex.com/docs/rest-auth"
        data = self._get_cached_or_fetch(url, "order_types")

        # Manuellt definierade ordertyper (eftersom dessa kan vara svåra att skrapa)
        self.order_types = {
            "EXCHANGE LIMIT": {
                "name": "EXCHANGE LIMIT",
                "description": "Limit order för exchange wallets",
                "required_params": ["symbol", "amount", "price"],
                "optional_params": [
                    "price_trailing",
                    "price_aux_limit",
                    "price_oco_stop",
                    "flags",
                ],
            },
            "EXCHANGE MARKET": {
                "name": "EXCHANGE MARKET",
                "description": "Market order för exchange wallets",
                "required_params": ["symbol", "amount"],
                "optional_params": ["price", "flags"],
            },
            "EXCHANGE STOP": {
                "name": "EXCHANGE STOP",
                "description": "Stop order för exchange wallets",
                "required_params": ["symbol", "amount", "price"],
                "optional_params": ["price_trailing", "price_aux_limit", "flags"],
            },
            "EXCHANGE TRAILING STOP": {
                "name": "EXCHANGE TRAILING STOP",
                "description": "Trailing stop order för exchange wallets",
                "required_params": ["symbol", "amount", "price_trailing"],
                "optional_params": ["price_aux_limit", "flags"],
            },
        }

        return self.order_types

    def get_endpoint_info(
        self, path: str, section: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Hämtar information om en specifik endpoint.

        Args:
            path: API-sökväg
            section: API-sektion (om känd)

        Returns:
            Dict med information om endpointen eller None om den inte hittas
        """
        if section:
            key = f"{section}:{path}"
            return self.endpoints.get(key)

        # Sök i alla sektioner
        for key, endpoint in self.endpoints.items():
            if endpoint.get("path") == path:
                return endpoint

        return None

    def get_error_info(self, code: str) -> Optional[Dict]:
        """
        Hämtar information om en specifik felkod.

        Args:
            code: Felkod

        Returns:
            Dict med information om felkoden eller None om den inte hittas
        """
        return self.error_codes.get(code)

    def get_order_type_info(self, order_type: str) -> Optional[Dict]:
        """
        Hämtar information om en specifik ordertyp.

        Args:
            order_type: Ordertyp

        Returns:
            Dict med information om ordertypen eller None om den inte hittas
        """
        return self.order_types.get(order_type.upper())

    def get_paper_trading_symbols(self) -> List[Dict]:
        """
        Hämtar symboler för paper trading.

        Returns:
            Lista med paper trading symboler
        """
        return [s for s in self.symbols if s.get("is_paper", False)]

    def generate_documentation_summary(self) -> Dict[str, Any]:
        """
        Genererar en sammanfattning av all dokumentation.

        Returns:
            Dict med sammanfattning av dokumentationen
        """
        return {
            "endpoints_count": len(self.endpoints),
            "error_codes_count": len(self.error_codes),
            "symbols_count": len(self.symbols),
            "order_types_count": len(self.order_types),
            "sections": API_SECTIONS,
            "last_updated": datetime.now().isoformat(),
        }


def main():
    """
    Huvudfunktion för att demonstrera användning av BitfinexDocsScraper.
    """
    scraper = BitfinexDocsScraper()

    # Hämta all dokumentation
    logger.info("Hämtar Bitfinex API-dokumentation...")
    scraper.fetch_all_documentation()
    scraper.fetch_error_codes()
    scraper.fetch_symbols()
    scraper.fetch_order_types()

    # Generera sammanfattning
    summary = scraper.generate_documentation_summary()
    logger.info(f"Dokumentationssammanfattning: {json.dumps(summary, indent=2)}")

    # Exempel på användning
    logger.info("Exempel på ordertyper:")
    for order_type, info in scraper.order_types.items():
        logger.info(f"  {order_type}: {info['description']}")
        logger.info(f"    Krävda parametrar: {', '.join(info['required_params'])}")

    logger.info("Exempel på paper trading symboler:")
    for symbol in scraper.get_paper_trading_symbols():
        logger.info(f"  {symbol['symbol']}")

    logger.info("Skrapning av dokumentation slutförd.")


if __name__ == "__main__":
    main()

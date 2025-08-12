"""
Bitfinex API Authentication Documentation Scraper

Denna modul hämtar och strukturerar information om autentisering för
Bitfinex API (REST och WebSocket). Används för att tillhandahålla korrekt
autentiseringsinformation och exempel för både rest/auth.py och ws/auth.py.
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
logger = logging.getLogger("bitfinex_auth_scraper")

# Konstanter
CACHE_DIR = Path(__file__).parent.parent / "cache" / "bitfinex_docs"
CACHE_VALIDITY_DAYS = 7  # Hur länge cache är giltig innan uppdatering
REST_AUTH_URL = "https://docs.bitfinex.com/docs/rest-auth"
WS_AUTH_URL = "https://docs.bitfinex.com/docs/ws-auth"


class BitfinexAuthScraper:
    """
    Klass för att skrapa och strukturera Bitfinex API autentiseringsdokumentation.
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
            {"User-Agent": "Mozilla/5.0 Genesis-Trading-Bot Authentication Helper"}
        )

        # Skapa cache-katalog om den inte finns
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initiera data-strukturer
        self.rest_auth_info: Dict[str, Any] = {}
        self.ws_auth_info: Dict[str, Any] = {}

    def _get_cached_or_fetch(self, url: str, section: str) -> dict:
        """
        Hämtar data från cache eller från webben om cachen är för gammal.

        Args:
            url: URL att hämta
            section: Sektion för cachelagring

        Returns:
            Dict med hämtad data
        """
        cache_file = self.cache_dir / f"{section}_auth.json"

        # Kontrollera om cachen finns och är giltig
        if cache_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(
                cache_file.stat().st_mtime
            )
            if file_age < timedelta(days=self.cache_validity_days):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        logger.info(f"Använder cachad data för {section}_auth")
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Fel vid läsning av cache: {e}")

        # Hämta från webben
        logger.info(f"Hämtar {section}_auth från {url}")
        try:
            response = self.session.get(url)
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
                            f"Använder gammal cache för {section}_auth på grund av nätverksfel"
                        )
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            # Returnera tom data om inget annat fungerar
            return {}

    def _parse_rest_auth_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyserar HTML-innehåll för REST autentiseringsdokumentation.

        Args:
            html_content: HTML-innehåll att analysera

        Returns:
            Strukturerad data om REST autentisering
        """
        soup = BeautifulSoup(html_content, "html.parser")
        result = {
            "section": "rest_auth",
            "auth_method": "HMAC-SHA384",
            "auth_headers": [],
            "nonce_info": {},
            "examples": [],
            "warnings": [],
            "endpoints": [],
        }

        # Extrahera autentiseringsheaders
        header_section = soup.find(string=re.compile("HTTP headers", re.IGNORECASE))
        if header_section and header_section.parent:
            header_list = header_section.parent.find_next("ul")
            if header_list:
                for item in header_list.find_all("li"):
                    header_text = item.get_text(strip=True)
                    result["auth_headers"].append(header_text)

        # Extrahera nonce-information
        nonce_section = soup.find(string=re.compile("Nonce", re.IGNORECASE))
        if nonce_section and nonce_section.parent:
            nonce_p = nonce_section.parent.find_next("p")
            if nonce_p:
                result["nonce_info"]["description"] = nonce_p.get_text(strip=True)

            # Leta efter varningar om nonce
            nonce_warning = soup.find(
                string=re.compile("nonce provided must be strictly", re.IGNORECASE)
            )
            if nonce_warning:
                result["nonce_info"]["warning"] = nonce_warning.get_text(strip=True)

        # Extrahera exempel-kod för autentisering
        code_blocks = soup.find_all("pre")
        for block in code_blocks:
            if "apiKey" in block.get_text() or "API_KEY" in block.get_text():
                lang = "unknown"
                if block.parent and block.parent.get("class"):
                    parent_classes = block.parent.get("class")
                    if "language-javascript" in parent_classes:
                        lang = "javascript"
                    elif "language-python" in parent_classes:
                        lang = "python"

                result["examples"].append(
                    {"language": lang, "code": block.get_text(strip=True)}
                )

        # Extrahera autentiseringsprocessen
        auth_process = soup.find(
            string=re.compile("authentication procedure", re.IGNORECASE)
        )
        if auth_process and auth_process.parent:
            process_list = auth_process.parent.find_next("ul")
            if process_list:
                steps = []
                for item in process_list.find_all("li"):
                    steps.append(item.get_text(strip=True))
                result["auth_process"] = steps

        # Extrahera tillgängliga autentiserade endpoints
        # Leta efter sektioner med endpoints
        endpoint_sections = []

        # Hitta rubriker som innehåller "Wallets", "Orders", "Positions", etc.
        # Leta först efter "REST Authenticated Endpoints" rubriken
        rest_auth_header = soup.find(
            string=lambda text: text
            and isinstance(text, str)
            and "REST Authenticated Endpoints" in text
        )

        # Om vi hittar rubriken, leta efter alla strong-taggar som innehåller kategorinamn
        if rest_auth_header and rest_auth_header.parent:
            endpoint_headers = []

            # Hitta alla strong-taggar i dokumentet
            all_strongs = soup.find_all("strong")

            # Filtrera ut de som innehåller kategorinamn som "Wallets", "Orders", etc.
            for strong in all_strongs:
                text = strong.get_text(strip=True)
                if any(
                    keyword in text
                    for keyword in [
                        "Wallets",
                        "Orders",
                        "Positions",
                        "Margin",
                        "Funding",
                        "Account",
                        "Merchants",
                    ]
                ):
                    endpoint_headers.append(strong)
        else:
            # Fallback till att leta efter specifika nyckelord i h3/h4
            endpoint_headers = soup.find_all(
                ["h3", "h4"],
                string=lambda text: text
                and any(
                    keyword in text
                    for keyword in [
                        "Wallets",
                        "Orders",
                        "Positions",
                        "Margin",
                        "Funding",
                        "Account",
                    ]
                ),
            )

        for header in endpoint_headers:
            section = {"category": header.get_text(strip=True), "endpoints": []}

            # Hitta listan med endpoints som följer denna rubrik
            endpoint_list = None

            # Om det är en strong-tag, leta efter nästa ul
            if header.name == "strong":
                endpoint_list = header.find_next("ul")
            # Om det är en annan typ av tag, leta efter en ul inuti den
            else:
                endpoint_list = header.find("ul")

            # Om vi inte hittar en ul inuti, leta efter nästa ul
            if not endpoint_list:
                endpoint_list = header.find_next("ul")

            if endpoint_list and hasattr(endpoint_list, "find_all"):
                for item in endpoint_list.find_all("li"):
                    # Hämta länken om den finns
                    link = item.find("a")
                    endpoint_name = item.get_text(strip=True)
                    endpoint_url = link.get("href") if link else None

                    section["endpoints"].append(
                        {"name": endpoint_name, "url": endpoint_url}
                    )

            if section["endpoints"]:
                endpoint_sections.append(section)

        result["endpoint_sections"] = endpoint_sections

        return result

    def _parse_ws_auth_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyserar HTML-innehåll för WebSocket autentiseringsdokumentation.

        Args:
            html_content: HTML-innehåll att analysera

        Returns:
            Strukturerad data om WebSocket autentisering
        """
        soup = BeautifulSoup(html_content, "html.parser")
        result = {
            "section": "ws_auth",
            "auth_method": "HMAC-SHA384",
            "auth_parameters": [],
            "nonce_info": {},
            "examples": [],
            "warnings": [],
            "channels": [],
        }

        # Extrahera autentiseringsparametrar
        param_table = soup.find("table")
        if param_table:
            rows = param_table.find_all("tr")[1:]  # Skippa header
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    param = {
                        "field": cells[0].get_text(strip=True),
                        "type": cells[1].get_text(strip=True),
                        "description": cells[2].get_text(strip=True),
                    }
                    result["auth_parameters"].append(param)

        # Extrahera nonce-information
        for param in result["auth_parameters"]:
            if param["field"] == "authNonce":
                result["nonce_info"]["description"] = param["description"]
                break

        # Leta efter varningar om nonce
        nonce_warning = soup.find(string=re.compile("MAX_SAFE_INTEGER", re.IGNORECASE))
        if nonce_warning and nonce_warning.parent:
            result["nonce_info"]["warning"] = nonce_warning.parent.get_text(strip=True)

        # Extrahera exempel-kod för autentisering
        auth_example_links = soup.find_all(
            "a", href=re.compile("authenticated-connection-example", re.IGNORECASE)
        )
        for link in auth_example_links:
            lang = "unknown"
            if "javascript" in link.get_text(strip=True).lower():
                lang = "javascript"
            elif "python" in link.get_text(strip=True).lower():
                lang = "python"

            result["examples"].append(
                {
                    "language": lang,
                    "link": link.get("href"),
                    "title": link.get_text(strip=True),
                }
            )

        # Extrahera tillgängliga autentiserade kanaler och events
        # Leta efter "List of Account Info Events" och "List of WS Inputs"
        event_sections = []

        # Hitta rubriker för event-sektioner
        # Leta specifikt efter "List of Account Info Events" och "List of WS Inputs"
        # Sök efter alla h3-taggar och filtrera dem
        h3_tags = soup.find_all("h3")
        list_of_account_header = None
        list_of_ws_header = None

        for h3 in h3_tags:
            text = h3.get_text(strip=True)
            if "List of Account Info Events" in text:
                list_of_account_header = h3
            elif "List of WS Inputs" in text:
                list_of_ws_header = h3

        event_headers = []
        if list_of_account_header:
            event_headers.append(list_of_account_header)
        if list_of_ws_header:
            event_headers.append(list_of_ws_header)

        # Fallback om vi inte hittar de specifika rubrikerna
        if not event_headers:
            event_headers = soup.find_all(
                ["h3"],
                string=lambda text: text
                and any(
                    keyword in text.lower()
                    for keyword in ["list of account", "list of ws"]
                ),
            )

        for header in event_headers:
            section = {"category": header.get_text(strip=True), "events": []}

            # Hitta listan med events som följer denna rubrik
            event_list = None

            # Om det är en h3/h4-tag, leta efter nästa ul
            if hasattr(header, "name") and header.name in ["h3", "h4"]:
                event_list = header.find_next("ul")
            # Om det är en annan typ av tag, leta efter en ul inuti den
            else:
                event_list = header.find("ul")

            # Om vi inte hittar en ul inuti, leta efter nästa ul
            if not event_list:
                event_list = header.find_next("ul")

            if event_list and hasattr(event_list, "find_all"):
                for item in event_list.find_all("li"):
                    # Hämta länken om den finns
                    link = item.find("a")
                    event_name = item.get_text(strip=True)
                    event_url = link.get("href") if link else None

                    section["events"].append({"name": event_name, "url": event_url})

            if section["events"]:
                event_sections.append(section)

        result["event_sections"] = event_sections

        # Extrahera information om channel filters
        filter_section = soup.find(string=re.compile("Channel Filters", re.IGNORECASE))
        if filter_section and filter_section.parent:
            filter_info = {}

            # Hitta beskrivning
            description_p = filter_section.parent.find_next("p")
            if description_p:
                filter_info["description"] = description_p.get_text(strip=True)

            # Hitta exempel på filter
            code_block = filter_section.parent.find_next("pre")
            if code_block:
                filter_info["example"] = code_block.get_text(strip=True)

            result["channel_filters"] = filter_info

        return result

    def fetch_rest_auth_info(self) -> Dict[str, Any]:
        """
        Hämtar information om REST API autentisering.

        Returns:
            Dict med information om REST API autentisering
        """
        data = self._get_cached_or_fetch(REST_AUTH_URL, "rest")

        if "html" in data:
            self.rest_auth_info = self._parse_rest_auth_html(data["html"])

        return self.rest_auth_info

    def fetch_ws_auth_info(self) -> Dict[str, Any]:
        """
        Hämtar information om WebSocket API autentisering.

        Returns:
            Dict med information om WebSocket API autentisering
        """
        data = self._get_cached_or_fetch(WS_AUTH_URL, "ws")

        if "html" in data:
            self.ws_auth_info = self._parse_ws_auth_html(data["html"])

        return self.ws_auth_info

    def get_auth_recommendations(self) -> Dict[str, Any]:
        """
        Sammanställer rekommendationer för autentisering baserat på dokumentationen.

        Returns:
            Dict med rekommendationer för REST och WebSocket autentisering
        """
        # Standardrekommendationer baserade på nuvarande implementering
        recommendations = {
            "rest": {
                "headers": {
                    "api_key": "bfx-apikey",
                    "nonce": "bfx-nonce",
                    "signature": "bfx-signature",
                },
                "nonce_generation": "Timestamp i mikrosekunder (timestamp * 1_000_000)",
                "message_format": "'/api/v2/{endpoint}{nonce}' + (JSON payload om det finns)",
                "signature_generation": "HMAC-SHA384(API_SECRET, message).hexdigest()",
            },
            "websocket": {
                "payload_format": {
                    "nonce": "authNonce",
                    "payload": "authPayload",
                    "signature": "authSig",
                    "api_key": "apiKey",
                    "event": "auth",
                },
                "nonce_generation": "Timestamp i millisekunder (timestamp * 1000)",
                "message_format": "AUTH{nonce}",
                "signature_generation": "HMAC-SHA384(API_SECRET, payload).hexdigest()",
            },
        }

        # Uppdatera med information från dokumentationen om tillgänglig
        if self.rest_auth_info:
            auth_headers = self.rest_auth_info.get("auth_headers", [])
            for header in auth_headers:
                if "apikey" in header.lower():
                    recommendations["rest"]["headers"]["api_key"] = "bfx-apikey"
                elif "nonce" in header.lower():
                    recommendations["rest"]["headers"]["nonce"] = "bfx-nonce"
                elif "signature" in header.lower():
                    recommendations["rest"]["headers"]["signature"] = "bfx-signature"

            nonce_info = self.rest_auth_info.get("nonce_info", {})
            if nonce_info.get("description"):
                recommendations["rest"]["nonce_info"] = nonce_info.get("description")

            auth_process = self.rest_auth_info.get("auth_process", [])
            for step in auth_process:
                if "payload" in step.lower():
                    message_format = step
                    recommendations["rest"]["message_format"] = message_format
                elif "signature" in step.lower() and "hmac" in step.lower():
                    sig_gen = step
                    recommendations["rest"]["signature_generation"] = sig_gen

        # WebSocket rekommendationer
        if self.ws_auth_info:
            for param in self.ws_auth_info.get("auth_parameters", []):
                field = param.get("field")
                if field == "authNonce":
                    recommendations["websocket"]["payload_format"][
                        "nonce"
                    ] = "authNonce"
                elif field == "authPayload":
                    recommendations["websocket"]["payload_format"][
                        "payload"
                    ] = "authPayload"
                elif field == "authSig":
                    recommendations["websocket"]["payload_format"][
                        "signature"
                    ] = "authSig"
                elif field == "apiKey":
                    recommendations["websocket"]["payload_format"]["api_key"] = "apiKey"

            nonce_info = self.ws_auth_info.get("nonce_info", {})
            if nonce_info.get("description"):
                recommendations["websocket"]["nonce_info"] = nonce_info.get(
                    "description"
                )

        return recommendations

    def generate_auth_code_examples(self) -> Dict[str, Any]:
        """
        Genererar kodexempel för autentisering baserat på dokumentationen.

        Returns:
            Dict med kodexempel för REST och WebSocket autentisering
        """
        examples = {
            "rest": {"python": {"build_auth_headers": ""}},
            "websocket": {"python": {"build_ws_auth_payload": ""}},
        }

        # REST Python exempel
        examples["rest"]["python"][
            "build_auth_headers"
        ] = """
def build_auth_headers(endpoint: str, payload: dict = None) -> dict:
    \"\"\"
    Bygger autentiseringsheaders för Bitfinex REST v2 API.
    
    Args:
        endpoint: API endpoint (t.ex. 'auth/r/orders')
        payload: Optional payload för POST-requests
        
    Returns:
        dict: Headers med nonce, signature och API-key
    \"\"\"
    # Använd timestamp med mikrosekunder för nonce
    nonce = str(int(datetime.now().timestamp() * 1_000_000))
    
    # Bygg message enligt Bitfinex dokumentation
    message = f"/api/v2/{endpoint}{nonce}"
    
    if payload is not None:
        message += json.dumps(payload)

    signature = hmac.new(
        key=API_SECRET.encode(),
        msg=message.encode(),
        digestmod=hashlib.sha384
    ).hexdigest()

    return {
        "bfx-apikey": API_KEY,
        "bfx-nonce": nonce,
        "bfx-signature": signature,
        "Content-Type": "application/json"
    }
"""

        # WebSocket Python exempel
        examples["websocket"]["python"][
            "build_ws_auth_payload"
        ] = """
def build_ws_auth_payload() -> str:
    \"\"\"
    Skapar autentiseringsmeddelande för Bitfinex WebSocket v2.
    
    Returns:
        str: JSON-formaterat auth-meddelande
    \"\"\"
    nonce = str(int(datetime.now().timestamp() * 1000))
    payload = f'AUTH{nonce}'
    
    signature = hmac.new(
        key=API_SECRET.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha384
    ).hexdigest()

    message = {
        "event": "auth",
        "apiKey": API_KEY,
        "authNonce": nonce,
        "authPayload": payload,
        "authSig": signature
    }

    return json.dumps(message)
"""

        return examples

    def compare_with_current_implementation(
        self, rest_auth_code: str = None, ws_auth_code: str = None
    ) -> Dict[str, Any]:
        """
        Jämför aktuell implementation med rekommendationer.

        Args:
            rest_auth_code: Nuvarande kod för REST auth
            ws_auth_code: Nuvarande kod för WebSocket auth

        Returns:
            Dict med skillnader och rekommendationer
        """
        results = {
            "rest": {"matches_recommendations": True, "differences": []},
            "websocket": {"matches_recommendations": True, "differences": []},
        }

        # Hämta rekommendationer
        recommendations = self.get_auth_recommendations()

        # Jämför REST implementation
        if rest_auth_code:
            # Kontrollera nonce-generering
            if (
                "timestamp() * 1_000_000" not in rest_auth_code
                and "mikrosekunder" in recommendations["rest"]["nonce_generation"]
            ):
                results["rest"]["matches_recommendations"] = False
                results["rest"]["differences"].append(
                    {
                        "type": "nonce_generation",
                        "recommendation": "Använd mikrosekunder för nonce (timestamp * 1_000_000)",
                    }
                )

            # Kontrollera message-format
            if "/api/v2/{endpoint}{nonce}" not in rest_auth_code.replace(" ", ""):
                results["rest"]["matches_recommendations"] = False
                results["rest"]["differences"].append(
                    {
                        "type": "message_format",
                        "recommendation": "Använd format: '/api/v2/{endpoint}{nonce}' + JSON payload",
                    }
                )

            # Kontrollera headers
            for key, value in recommendations["rest"]["headers"].items():
                if value not in rest_auth_code:
                    results["rest"]["matches_recommendations"] = False
                    results["rest"]["differences"].append(
                        {"type": "header", "recommendation": f"Använd header: {value}"}
                    )

        # Jämför WebSocket implementation
        if ws_auth_code:
            # Kontrollera nonce-generering
            if (
                "timestamp() * 1000" not in ws_auth_code
                and "millisekunder" in recommendations["websocket"]["nonce_generation"]
            ):
                results["websocket"]["matches_recommendations"] = False
                results["websocket"]["differences"].append(
                    {
                        "type": "nonce_generation",
                        "recommendation": "Använd millisekunder för nonce (timestamp * 1000)",
                    }
                )

            # Kontrollera message-format
            if (
                "AUTH{nonce}" not in ws_auth_code.replace(" ", "")
                and "payload = f'AUTH{nonce}'" not in ws_auth_code
            ):
                results["websocket"]["matches_recommendations"] = False
                results["websocket"]["differences"].append(
                    {
                        "type": "message_format",
                        "recommendation": "Använd format: 'AUTH{nonce}'",
                    }
                )

            # Kontrollera payload-format
            for key, value in recommendations["websocket"]["payload_format"].items():
                if value not in ws_auth_code:
                    results["websocket"]["matches_recommendations"] = False
                    results["websocket"]["differences"].append(
                        {
                            "type": "payload_format",
                            "recommendation": f"Inkludera fält: {value}",
                        }
                    )

        return results


def main():
    """
    Huvudfunktion för att demonstrera användning av BitfinexAuthScraper.
    """
    scraper = BitfinexAuthScraper()

    # Hämta autentiseringsinformation
    logger.info("Hämtar Bitfinex API autentiseringsdokumentation...")
    rest_info = scraper.fetch_rest_auth_info()
    ws_info = scraper.fetch_ws_auth_info()

    # Generera rekommendationer
    recommendations = scraper.get_auth_recommendations()
    logger.info(
        f"REST autentiseringsrekommendationer: {json.dumps(recommendations['rest'], indent=2)}"
    )
    logger.info(
        f"WebSocket autentiseringsrekommendationer: {json.dumps(recommendations['websocket'], indent=2)}"
    )

    # Generera kodexempel
    examples = scraper.generate_auth_code_examples()
    logger.info(
        f"REST autentiseringskodexempel:\n{examples['rest']['python']['build_auth_headers']}"
    )
    logger.info(
        f"WebSocket autentiseringskodexempel:\n{examples['websocket']['python']['build_ws_auth_payload']}"
    )

    # Visa tillgängliga REST endpoints
    if "endpoint_sections" in rest_info:
        logger.info("\n=== Tillgängliga REST API Endpoints ===")
        for section in rest_info["endpoint_sections"]:
            logger.info(f"\n## {section['category']}")
            for endpoint in section["endpoints"]:
                logger.info(f"- {endpoint['name']}")

    # Visa tillgängliga WebSocket events
    if "event_sections" in ws_info:
        logger.info("\n=== Tillgängliga WebSocket Events ===")
        for section in ws_info["event_sections"]:
            logger.info(f"\n## {section['category']}")
            for event in section["events"]:
                logger.info(f"- {event['name']}")

    logger.info("\nSkrapning av autentiseringsdokumentation slutförd.")


if __name__ == "__main__":
    main()

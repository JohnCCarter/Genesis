import html
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ApiParameter:
    """Representerar en API-parameter"""

    name: str
    type: str
    required: bool
    description: str
    default: Optional[Any] = None
    example: Optional[Any] = None


@dataclass
class ApiResponse:
    """Representerar ett API-svar"""

    type: str
    description: str
    schema: Dict[str, Any]
    examples: List[Any]


@dataclass
class ApiEndpoint:
    """Representerar en API-endpoint"""

    method: str
    path: str
    description: str
    authentication: bool
    parameters: List[ApiParameter]
    response: ApiResponse
    rate_limit: Optional[str] = None
    category: str = ""
    subcategory: str = ""


class BitfinexApiExtractor:
    def __init__(self, cache_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar API-extraktorn

        Args:
            cache_dir: Sökväg till cache-katalogen
        """
        self.cache_dir = Path(cache_dir)
        self.api_dir = self.cache_dir / "api"
        self.api_dir.mkdir(parents=True, exist_ok=True)

        # Skapa undermappar för olika API-typer
        self.rest_dir = self.api_dir / "rest"
        self.ws_dir = self.api_dir / "websocket"
        self.auth_dir = self.api_dir / "auth"

        for dir in [self.rest_dir, self.ws_dir, self.auth_dir]:
            dir.mkdir(exist_ok=True)

    def read_file_chunks(
        self, file_path: Path, chunk_size: int = 8192
    ) -> Iterator[str]:
        """
        Läser en fil i chunks

        Args:
            file_path: Sökväg till filen
            chunk_size: Storlek på varje chunk

        Yields:
            Chunks av filinnehållet
        """
        with file_path.open("r", encoding="utf-8") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def extract_api_info_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extraherar API-information från HTML

        Args:
            html_content: HTML-innehåll att analysera

        Returns:
            Lista med API-information
        """
        soup = BeautifulSoup(html_content, "html.parser")
        api_info = []

        # Hitta alla data-initial-props attribut som innehåller API-information
        for element in soup.find_all(attrs={"data-initial-props": True}):
            try:
                # Extrahera och avkoda JSON-data
                data_str = html.unescape(element["data-initial-props"])
                data = json.loads(data_str)

                # Kontrollera om det är API-dokumentation
                if isinstance(data, dict) and (
                    "endpoints" in data or "methods" in data
                ):
                    api_info.append(data)

            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"Kunde inte parsa data-initial-props: {str(e)}")
                continue

        # Om ingen data hittades i data-initial-props, försök hitta i script-taggar
        if not api_info:
            for script in soup.find_all("script", type="application/json"):
                try:
                    if script.string:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and (
                            "endpoints" in data or "methods" in data
                        ):
                            api_info.append(data)
                except json.JSONDecodeError as e:
                    logger.debug(f"Kunde inte parsa script JSON: {str(e)}")
                    continue

        return api_info

    def extract_endpoints_from_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extraherar endpoints från API-data

        Args:
            data: API-data att analysera

        Returns:
            Lista med endpoints
        """
        endpoints = []

        # Hantera olika datastrukturer
        if "endpoints" in data:
            raw_endpoints = data["endpoints"]
        elif "methods" in data:
            raw_endpoints = data["methods"]
        else:
            return endpoints

        # Bearbeta varje endpoint
        for raw in raw_endpoints:
            try:
                endpoint = {
                    "method": raw.get("method", "").upper(),
                    "path": raw.get("path", ""),
                    "description": raw.get("description", ""),
                    "authentication": raw.get("authentication", False),
                    "parameters": self._extract_parameters_from_data(raw),
                    "response": self._extract_response_from_data(raw),
                    "rate_limit": raw.get("rate_limit"),
                }

                # Lägg bara till om vi har både metod och sökväg
                if endpoint["method"] and endpoint["path"]:
                    endpoints.append(endpoint)

            except Exception as e:
                logger.error(f"Fel vid extrahering av endpoint: {str(e)}")
                continue

        return endpoints

    def _extract_parameters_from_data(
        self, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extraherar parametrar från endpoint-data"""
        parameters = []

        raw_params = data.get("parameters", [])
        if isinstance(raw_params, dict):
            raw_params = [{"name": k, **v} for k, v in raw_params.items()]

        for param in raw_params:
            try:
                parameter = {
                    "name": param.get("name", ""),
                    "type": param.get("type", ""),
                    "required": param.get("required", False),
                    "description": param.get("description", ""),
                    "default": param.get("default"),
                    "example": param.get("example"),
                }

                if parameter["name"]:
                    parameters.append(parameter)

            except Exception as e:
                logger.error(f"Fel vid extrahering av parameter: {str(e)}")
                continue

        return parameters

    def _extract_response_from_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extraherar svarsinformation från endpoint-data"""
        response = data.get("response", {})
        if not isinstance(response, dict):
            response = {}

        return {
            "type": response.get("type", ""),
            "description": response.get("description", ""),
            "schema": response.get("schema", {}),
            "examples": response.get("examples", []),
        }

    def categorize_endpoint(self, endpoint: Dict[str, Any]) -> tuple[str, str]:
        """
        Kategoriserar en endpoint baserat på sökväg och metod

        Args:
            endpoint: Endpoint att kategorisera

        Returns:
            Tuple med huvudkategori och underkategori
        """
        path = endpoint["path"].lower()

        # Websocket endpoints
        if "ws" in path or "websocket" in path:
            if endpoint["authentication"]:
                return "websocket", "authenticated"
            return "websocket", "public"

        # REST endpoints
        if endpoint["authentication"]:
            if "order" in path:
                return "rest", "orders"
            elif "position" in path:
                return "rest", "positions"
            elif "wallet" in path:
                return "rest", "wallets"
            elif "margin" in path:
                return "rest", "margin"
            return "rest", "authenticated"
        return "rest", "public"

    def save_endpoint(
        self, endpoint: Dict[str, Any], category: str, subcategory: str
    ) -> None:
        """
        Sparar en endpoint i rätt kategori

        Args:
            endpoint: Endpoint att spara
            category: Huvudkategori
            subcategory: Underkategori
        """
        # Välj rätt katalog
        if category == "websocket":
            base_dir = self.ws_dir
        else:
            base_dir = self.rest_dir

        # Skapa underkatalog
        subdir = base_dir / subcategory
        subdir.mkdir(exist_ok=True)

        # Skapa filnamn från sökväg
        path_parts = endpoint["path"].strip("/").split("/")
        filename = "_".join(path_parts) + ".json"

        # Spara endpoint
        filepath = subdir / filename
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(endpoint, f, indent=2, ensure_ascii=False)

        logger.info(f"Sparade {category}/{subcategory}/{filename}")

    def create_index(self) -> None:
        """Skapar en index-fil för alla API-endpoints"""
        index = {
            "title": "Bitfinex API Documentation",
            "description": "Komplett dokumentation för Bitfinex API",
            "categories": {},
        }

        # Samla information från alla kategorier
        for category_dir in [self.rest_dir, self.ws_dir]:
            category = category_dir.name
            index["categories"][category] = {}

            for subdir in category_dir.glob("*"):
                if not subdir.is_dir():
                    continue

                subcategory = subdir.name
                endpoints = []

                for file in subdir.glob("*.json"):
                    with file.open("r", encoding="utf-8") as f:
                        data = json.load(f)

                    endpoints.append(
                        {
                            "method": data["method"],
                            "path": data["path"],
                            "description": data["description"],
                            "authentication": data["authentication"],
                            "file": file.name,
                        }
                    )

                index["categories"][category][subcategory] = {
                    "count": len(endpoints),
                    "endpoints": sorted(endpoints, key=lambda x: x["path"]),
                }

        # Spara index
        with (self.api_dir / "index.json").open("w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        logger.info("Skapade api/index.json")

    def process_file(self, file_path: Path) -> None:
        """
        Bearbetar en fil och extraherar API-information

        Args:
            file_path: Sökväg till filen
        """
        try:
            logger.info(f"Bearbetar {file_path}")

            # Läs fil i chunks
            content = []
            for chunk in self.read_file_chunks(file_path):
                content.append(chunk)
            content = "".join(content)

            # Extrahera API-information från HTML
            api_data_list = self.extract_api_info_from_html(content)

            if not api_data_list:
                logger.warning(f"Ingen API-data hittades i {file_path}")
                return

            # Bearbeta varje API-data
            for api_data in api_data_list:
                # Extrahera endpoints
                endpoints = self.extract_endpoints_from_data(api_data)

                if not endpoints:
                    continue

                # Bearbeta varje endpoint
                for endpoint in endpoints:
                    # Kategorisera endpoint
                    category, subcategory = self.categorize_endpoint(endpoint)

                    # Spara endpoint
                    self.save_endpoint(endpoint, category, subcategory)

        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def process_all_files(self) -> None:
        """Bearbetar alla relevanta filer i cache-katalogen"""
        try:
            # Rensa api-katalogen
            if self.api_dir.exists():
                shutil.rmtree(self.api_dir)
            self.api_dir.mkdir(parents=True)

            # Återskapa struktur
            for dir in [self.rest_dir, self.ws_dir, self.auth_dir]:
                dir.mkdir(exist_ok=True)

            # Bearbeta API-filer
            api_files = [
                "rest_auth.json",
                "rest-public.json",
                "ws_auth.json",
                "ws-public.json",
            ]

            for filename in api_files:
                file_path = self.cache_dir / filename
                if file_path.exists():
                    self.process_file(file_path)

            # Skapa index
            self.create_index()

            logger.info("API-extrahering slutförd!")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {str(e)}")


def main():
    extractor = BitfinexApiExtractor()
    extractor.process_all_files()


if __name__ == "__main__":
    main()

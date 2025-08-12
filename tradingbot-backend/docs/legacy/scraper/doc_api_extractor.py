import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocApiExtractor:
    def __init__(self, input_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar API-extraktor för dokumentation

        Args:
            input_dir: Sökväg till input-katalogen
        """
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir / "api"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Skapa undermappar
        self.rest_dir = self.output_dir / "rest"
        self.ws_dir = self.output_dir / "websocket"

        for dir in [self.rest_dir, self.ws_dir]:
            dir.mkdir(exist_ok=True)

    def extract_api_info(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extraherar API-information från HTML

        Args:
            html_content: HTML att analysera

        Returns:
            Lista med API-information
        """
        soup = BeautifulSoup(html_content, "html.parser")
        api_info = []

        # Hitta titel och beskrivning
        title = ""
        description = ""

        title_elem = soup.find("title")
        if title_elem:
            title = title_elem.text.strip()

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "").strip()

        # Hitta alla pre/code-block
        for code_block in soup.find_all(["pre", "code"]):
            code_text = code_block.get_text()

            # Kontrollera om det är ett kodexempel
            if any(word in code_text.lower() for word in ["curl", "http", "request"]):
                # Extrahera endpoint från kodexempel
                endpoint = self._extract_endpoint_from_code(
                    code_text, title, description
                )
                if endpoint:
                    api_info.append(endpoint)

        # Om inga endpoints hittades, försök hitta i text
        if not api_info:
            # Hitta alla stycken
            for p in soup.find_all("p"):
                text = p.get_text()

                # Kontrollera om stycket innehåller API-information
                if any(word in text.lower() for word in ["api", "endpoint", "method"]):
                    # Extrahera endpoint från text
                    endpoint = self._extract_endpoint_from_text(
                        text, title, description
                    )
                    if endpoint:
                        api_info.append(endpoint)

        return api_info

    def _extract_endpoint_from_code(
        self, code: str, title: str, description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extraherar endpoint från kodexempel

        Args:
            code: Kodexempel att analysera
            title: Dokumentationens titel
            description: Dokumentationens beskrivning

        Returns:
            Endpoint-information eller None
        """
        try:
            # Hitta curl-kommando
            curl_match = re.search(
                r'curl\s+(?:-X\s+(\w+)\s+)?["\']?(https?://[^/]+)?(/[^"\'\s]+)', code
            )
            if curl_match:
                method = curl_match.group(1) or "GET"
                path = curl_match.group(3)

                # Skapa endpoint
                endpoint = {
                    "method": method.upper(),
                    "path": path,
                    "title": title,
                    "description": description,
                    "authentication": self._check_authentication(code),
                    "parameters": self._extract_parameters_from_code(code),
                    "response": self._extract_response_from_code(code),
                    "examples": [
                        {
                            "request": code,
                            "response": self._extract_response_example(code),
                        }
                    ],
                }

                return endpoint

        except Exception as e:
            logger.error(f"Fel vid extrahering av endpoint från kod: {str(e)}")
            return None

    def _extract_endpoint_from_text(
        self, text: str, title: str, description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extraherar endpoint från text

        Args:
            text: Text att analysera
            title: Dokumentationens titel
            description: Dokumentationens beskrivning

        Returns:
            Endpoint-information eller None
        """
        try:
            # Hitta metod och sökväg
            method_match = re.search(r'(GET|POST|PUT|DELETE)\s+(/[^\s"\']+)', text)
            if method_match:
                method = method_match.group(1)
                path = method_match.group(2)

                # Skapa endpoint
                endpoint = {
                    "method": method.upper(),
                    "path": path,
                    "title": title,
                    "description": description,
                    "authentication": self._check_authentication(text),
                    "parameters": self._extract_parameters_from_text(text),
                    "response": self._extract_response_from_text(text),
                    "examples": [],
                }

                return endpoint

        except Exception as e:
            logger.error(f"Fel vid extrahering av endpoint från text: {str(e)}")
            return None

    def _check_authentication(self, text: str) -> bool:
        """Kontrollerar om autentisering krävs"""
        auth_words = [
            "authenticated",
            "requires auth",
            "authorization required",
            "api key",
            "api-key",
            "secret",
            "token",
        ]

        return any(word in text.lower() for word in auth_words)

    def _extract_parameters_from_code(self, code: str) -> List[Dict[str, Any]]:
        """Extraherar parametrar från kodexempel"""
        parameters = []

        try:
            # Hitta JSON-data i curl-kommando
            json_match = re.search(r'-d\s+["\'](\{[^}]+\})["\']', code)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    if isinstance(data, dict):
                        for key, value in data.items():
                            param = {
                                "name": key,
                                "type": type(value).__name__,
                                "required": True,  # Anta att alla parametrar i exempel är obligatoriska
                                "description": "",
                                "example": value,
                            }
                            parameters.append(param)
                except json.JSONDecodeError:
                    pass

            # Hitta URL-parametrar
            params_match = re.search(r'\?([^"\'\s]+)', code)
            if params_match:
                params = params_match.group(1).split("&")
                for param in params:
                    if "=" in param:
                        name, value = param.split("=", 1)
                        param = {
                            "name": name,
                            "type": "string",
                            "required": False,  # Anta att URL-parametrar är valfria
                            "description": "",
                            "example": value,
                        }
                        parameters.append(param)

        except Exception as e:
            logger.error(f"Fel vid extrahering av parametrar från kod: {str(e)}")

        return parameters

    def _extract_parameters_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extraherar parametrar från text"""
        parameters = []

        try:
            # Hitta parameterbeskrivningar
            param_matches = re.finditer(
                r'[`"]([^`"]+)[`"]\s*(?:\((required|optional)\))?\s*[-:]\s*([^.]+)',
                text,
            )
            for match in param_matches:
                name = match.group(1)
                required = match.group(2) == "required" if match.group(2) else False
                description = match.group(3).strip()

                param = {
                    "name": name,
                    "type": "string",  # Standard-typ
                    "required": required,
                    "description": description,
                }
                parameters.append(param)

        except Exception as e:
            logger.error(f"Fel vid extrahering av parametrar från text: {str(e)}")

        return parameters

    def _extract_response_from_code(self, code: str) -> Dict[str, Any]:
        """Extraherar svarsinformation från kodexempel"""
        response = {"type": "", "description": "", "schema": {}, "examples": []}

        try:
            # Hitta JSON-svar
            json_matches = re.finditer(
                r"(?:Response:|Returns:|\{)[^}]*\}", code, re.DOTALL
            )
            for match in json_matches:
                try:
                    json_str = match.group(0)
                    if json_str.startswith(("Response:", "Returns:")):
                        json_str = json_str.split(":", 1)[1]
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        response["schema"] = data
                        response["examples"].append(data)
                        response["type"] = "application/json"
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error(f"Fel vid extrahering av svar från kod: {str(e)}")

        return response

    def _extract_response_from_text(self, text: str) -> Dict[str, Any]:
        """Extraherar svarsinformation från text"""
        response = {"type": "", "description": "", "schema": {}, "examples": []}

        try:
            # Hitta svarsbeskrivning
            response_match = re.search(r"(?:Response:|Returns:)\s*([^{]+)", text)
            if response_match:
                response["description"] = response_match.group(1).strip()

            # Hitta JSON-schema
            schema_match = re.search(r"\{[^}]+\}", text)
            if schema_match:
                try:
                    schema = json.loads(schema_match.group(0))
                    if isinstance(schema, dict):
                        response["schema"] = schema
                        response["type"] = "application/json"
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"Fel vid extrahering av svar från text: {str(e)}")

        return response

    def _extract_response_example(self, code: str) -> Optional[Dict[str, Any]]:
        """Extraherar svarsexempel från kodexempel"""
        try:
            # Hitta JSON-svar efter //
            example_match = re.search(
                r"//\s*(?:Response:|Returns:)?\s*(\{[^}]+\})", code
            )
            if example_match:
                try:
                    return json.loads(example_match.group(1))
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"Fel vid extrahering av svarsexempel: {str(e)}")
            return None

    def categorize_endpoint(
        self, endpoint: Dict[str, Any], source: str
    ) -> tuple[str, str]:
        """
        Kategoriserar en endpoint

        Args:
            endpoint: Endpoint att kategorisera
            source: Källfil

        Returns:
            Tuple med huvudkategori och underkategori
        """
        # Bestäm huvudkategori
        if "websocket" in source.lower() or "ws" in source.lower():
            category = "websocket"
        else:
            category = "rest"

        # Bestäm underkategori baserat på sökväg och autentisering
        path = endpoint.get("path", "").lower()

        if endpoint.get("authentication", False) or any(
            word in path for word in ["auth", "key", "private"]
        ):
            subcategory = "authenticated"
        else:
            subcategory = "public"

        return category, subcategory

    def save_endpoint(
        self, endpoint: Dict[str, Any], category: str, subcategory: str, source: str
    ) -> None:
        """
        Sparar en endpoint

        Args:
            endpoint: Endpoint att spara
            category: Huvudkategori
            subcategory: Underkategori
            source: Källfil
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
        path = endpoint["path"].strip("/")
        if not path:
            path = "unknown"
        filename = f"{path.replace('/', '_')}.json"

        # Lägg till källinformation
        endpoint["source"] = source

        # Spara endpoint
        filepath = subdir / filename
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(endpoint, f, indent=2, ensure_ascii=False)

        logger.info(f"Sparade {category}/{subcategory}/{filename}")

    def create_index(self) -> None:
        """Skapar en index-fil"""
        index = {
            "title": "Bitfinex API Documentation",
            "description": "Strukturerad API-dokumentation för Bitfinex",
            "categories": {
                "rest": self._index_category("rest"),
                "websocket": self._index_category("websocket"),
            },
        }

        # Spara index
        with (self.output_dir / "index.json").open("w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        logger.info("Skapade index.json")

    def _index_category(self, category: str) -> Dict[str, Any]:
        """Indexerar en kategori"""
        result = {"authenticated": {"endpoints": []}, "public": {"endpoints": []}}

        base_dir = self.rest_dir if category == "rest" else self.ws_dir
        if not base_dir.exists():
            return result

        for auth_type in ["authenticated", "public"]:
            subdir = base_dir / auth_type
            if not subdir.exists():
                continue

            endpoints = []
            for file in subdir.glob("*.json"):
                try:
                    with file.open("r", encoding="utf-8") as f:
                        data = json.load(f)

                    endpoints.append(
                        {
                            "method": data.get("method", ""),
                            "path": data.get("path", ""),
                            "title": data.get("title", ""),
                            "description": data.get("description", ""),
                            "source": data.get("source", ""),
                            "file": file.name,
                        }
                    )
                except Exception as e:
                    logger.error(f"Fel vid indexering av {file}: {str(e)}")

            result[auth_type]["endpoints"] = sorted(endpoints, key=lambda x: x["path"])
            result[auth_type]["count"] = len(endpoints)

        return result

    def process_file(self, file_path: Path) -> None:
        """
        Bearbetar en fil

        Args:
            file_path: Sökväg till filen
        """
        try:
            logger.info(f"Bearbetar {file_path}")

            # Läs fil
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Kontrollera om det är ett HTML-dokument
            if isinstance(data, dict) and "html" in data:
                # Extrahera API-information från HTML
                endpoints = self.extract_api_info(data["html"])
            else:
                # Använd data direkt
                endpoints = [data]

            if not endpoints:
                logger.warning(f"Inga endpoints hittades i {file_path}")
                return

            # Bearbeta varje endpoint
            for endpoint in endpoints:
                # Kategorisera endpoint
                category, subcategory = self.categorize_endpoint(
                    endpoint, file_path.stem
                )

                # Spara endpoint
                self.save_endpoint(endpoint, category, subcategory, file_path.stem)

        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def process_all_files(self) -> None:
        """Bearbetar alla filer"""
        try:
            # Rensa output-katalog
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True)

            # Återskapa struktur
            for dir in [self.rest_dir, self.ws_dir]:
                dir.mkdir(exist_ok=True)

            # Bearbeta alla filer
            for file_path in self.input_dir.glob("*.json"):
                self.process_file(file_path)

            # Skapa index
            self.create_index()

            logger.info("API-extrahering slutförd!")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {str(e)}")


def main():
    extractor = DocApiExtractor()
    extractor.process_all_files()


if __name__ == "__main__":
    main()

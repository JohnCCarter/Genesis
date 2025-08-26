import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HtmlApiExtractor:
    def __init__(self, input_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar HTML API-extraktor

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

        # Hitta alla API-sektioner
        for section in soup.find_all(
            ["div", "section"], class_=["api-section", "endpoint", "method"]
        ):
            # Extrahera endpoint-information
            endpoint = self._extract_endpoint(section)
            if endpoint:
                api_info.append(endpoint)

        # Om inga endpoints hittades, försök hitta i text
        if not api_info:
            # Hitta alla h2/h3 som kan vara API-titlar
            for heading in soup.find_all(["h2", "h3"]):
                # Kontrollera om rubriken innehåller API-relaterad text
                if any(word in heading.text.lower() for word in ["api", "endpoint", "method"]):
                    # Hitta nästa sektion
                    section = heading.find_next(["div", "section"])
                    if section:
                        endpoint = self._extract_endpoint_from_text(section)
                        if endpoint:
                            api_info.append(endpoint)

        return api_info

    def _extract_endpoint(self, section: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extraherar information från en endpoint-sektion

        Args:
            section: HTML-sektion att analysera

        Returns:
            Endpoint-information eller None
        """
        try:
            # Hitta metod och sökväg
            method = None
            path = None

            # Sök i olika format
            method_elem = section.find(
                ["span", "code"], class_=["method", "http-method", "api-method"]
            )
            if method_elem:
                method = method_elem.text.strip().upper()
            else:
                # Försök hitta i text
                text = section.get_text()
                methods = ["GET", "POST", "PUT", "DELETE"]
                for m in methods:
                    if m in text:
                        method = m
                        break

            path_elem = section.find(
                ["span", "code"], class_=["path", "endpoint", "url", "api-path"]
            )
            if path_elem:
                path = path_elem.text.strip()
            else:
                # Försök hitta URL-mönster
                text = section.get_text()
                urls = re.findall(r'/v[0-9]/[^\s"\']+', text)
                if urls:
                    path = urls[0]

            if not method or not path:
                return None

            # Skapa endpoint
            endpoint = {
                "method": method,
                "path": path,
                "description": self._extract_description(section),
                "authentication": self._check_authentication(section),
                "parameters": self._extract_parameters(section),
                "response": self._extract_response(section),
                "examples": self._extract_examples(section),
            }

            return endpoint

        except Exception as e:
            logger.error(f"Fel vid extrahering av endpoint: {str(e)}")
            return None

    def _extract_endpoint_from_text(self, section: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extraherar endpoint-information från text

        Args:
            section: HTML-sektion att analysera

        Returns:
            Endpoint-information eller None
        """
        try:
            text = section.get_text()

            # Hitta metod
            method = None
            methods = ["GET", "POST", "PUT", "DELETE"]
            for m in methods:
                if m in text:
                    method = m
                    break

            # Hitta sökväg
            path = None
            urls = re.findall(r'/v[0-9]/[^\s"\']+', text)
            if urls:
                path = urls[0]

            if not method or not path:
                return None

            # Skapa endpoint
            endpoint = {
                "method": method,
                "path": path,
                "description": self._extract_description(section),
                "authentication": self._check_authentication(section),
                "parameters": self._extract_parameters(section),
                "response": self._extract_response(section),
                "examples": self._extract_examples(section),
            }

            return endpoint

        except Exception as e:
            logger.error(f"Fel vid extrahering av endpoint från text: {str(e)}")
            return None

    def _extract_description(self, section: BeautifulSoup) -> str:
        """Extraherar beskrivning"""
        description = ""

        # Hitta beskrivning i olika format
        desc_elem = section.find(["p", "div"], class_=["description", "docs", "api-description"])
        if desc_elem:
            description = desc_elem.text.strip()
        else:
            # Försök hitta första stycket
            first_p = section.find("p")
            if first_p:
                description = first_p.text.strip()

        return description

    def _check_authentication(self, section: BeautifulSoup) -> bool:
        """Kontrollerar om autentisering krävs"""
        # Kontrollera text
        text = section.get_text().lower()
        auth_words = [
            "authenticated",
            "requires auth",
            "authorization required",
            "api key",
        ]

        return any(word in text for word in auth_words)

    def _extract_parameters(self, section: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar parametrar"""
        parameters = []

        # Hitta parametertabell eller lista
        param_section = section.find(
            ["table", "div", "ul"],
            class_=["parameters", "params", "arguments", "api-parameters"],
        )
        if not param_section:
            return parameters

        # Hitta alla parametrar
        for param in param_section.find_all(
            ["tr", "li", "div"], class_=["parameter", "argument", "api-parameter"]
        ):
            try:
                param_info = {
                    "name": "",
                    "type": "",
                    "required": False,
                    "description": "",
                    "default": None,
                    "example": None,
                }

                # Hitta namn
                name_elem = param.find(["td", "span", "code"], class_=["name", "param-name"])
                if name_elem:
                    param_info["name"] = name_elem.text.strip()

                # Hitta typ
                type_elem = param.find(["td", "span", "code"], class_=["type", "param-type"])
                if type_elem:
                    param_info["type"] = type_elem.text.strip()

                # Kontrollera om obligatorisk
                required_text = param.get_text().lower()
                param_info["required"] = (
                    "required" in required_text and "optional" not in required_text
                )

                # Hitta beskrivning
                desc_elem = param.find(["td", "span", "p"], class_=["description", "param-desc"])
                if desc_elem:
                    param_info["description"] = desc_elem.text.strip()

                # Hitta standardvärde
                default_elem = param.find(
                    ["td", "span", "code"], class_=["default", "param-default"]
                )
                if default_elem:
                    param_info["default"] = default_elem.text.strip()

                # Hitta exempel
                example_elem = param.find(
                    ["td", "span", "code"], class_=["example", "param-example"]
                )
                if example_elem:
                    param_info["example"] = example_elem.text.strip()

                if param_info["name"]:
                    parameters.append(param_info)

            except Exception as e:
                logger.error(f"Fel vid extrahering av parameter: {str(e)}")
                continue

        return parameters

    def _extract_response(self, section: BeautifulSoup) -> Dict[str, Any]:
        """Extraherar svarsinformation"""
        response = {"type": "", "description": "", "schema": {}, "examples": []}

        # Hitta svarssektion
        response_section = section.find(
            ["div", "section"], class_=["response", "returns", "result", "api-response"]
        )
        if not response_section:
            return response

        try:
            # Hitta typ
            type_elem = response_section.find(["span", "code"], class_=["type", "response-type"])
            if type_elem:
                response["type"] = type_elem.text.strip()

            # Hitta beskrivning
            desc_elem = response_section.find(["p", "div"], class_=["description", "response-desc"])
            if desc_elem:
                response["description"] = desc_elem.text.strip()

            # Hitta schema
            schema_elem = response_section.find(["pre", "code"], class_=["schema", "json-schema"])
            if schema_elem:
                try:
                    schema_text = schema_elem.text.strip()
                    if schema_text:
                        response["schema"] = json.loads(schema_text)
                except json.JSONDecodeError:
                    pass

            # Hitta exempel
            for example in response_section.find_all(
                ["pre", "code"], class_=["example", "json-example"]
            ):
                try:
                    example_text = example.text.strip()
                    if example_text:
                        response["examples"].append(json.loads(example_text))
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error(f"Fel vid extrahering av svar: {str(e)}")

        return response

    def _extract_examples(self, section: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar exempel"""
        examples = []

        # Hitta alla exempel
        for example in section.find_all(
            ["div", "section"], class_=["example", "sample", "api-example"]
        ):
            try:
                example_info = {
                    "title": "",
                    "description": "",
                    "request": {},
                    "response": {},
                }

                # Hitta titel
                title_elem = example.find(["h3", "h4", "strong"])
                if title_elem:
                    example_info["title"] = title_elem.text.strip()

                # Hitta beskrivning
                desc_elem = example.find("p")
                if desc_elem:
                    example_info["description"] = desc_elem.text.strip()

                # Hitta request
                request_elem = example.find(["pre", "code"], class_=["request", "curl"])
                if request_elem:
                    example_info["request"] = request_elem.text.strip()

                # Hitta response
                response_elem = example.find(["pre", "code"], class_=["response", "json"])
                if response_elem:
                    try:
                        response_text = response_elem.text.strip()
                        if response_text:
                            example_info["response"] = json.loads(response_text)
                    except json.JSONDecodeError:
                        example_info["response"] = response_text

                examples.append(example_info)

            except Exception as e:
                logger.error(f"Fel vid extrahering av exempel: {str(e)}")
                continue

        return examples

    def categorize_endpoint(self, endpoint: Dict[str, Any], source: str) -> tuple[str, str]:
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
                category, subcategory = self.categorize_endpoint(endpoint, file_path.stem)

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
    extractor = HtmlApiExtractor()
    extractor.process_all_files()


if __name__ == "__main__":
    main()

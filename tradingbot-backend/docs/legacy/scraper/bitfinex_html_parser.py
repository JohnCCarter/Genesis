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


class BitfinexHtmlParser:
    def __init__(self, input_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar HTML-parser

        Args:
            input_dir: Sökväg till input-katalogen
        """
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir / "parsed"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_html(self, html_content: str) -> Dict[str, Any]:
        """
        Parsar HTML-innehåll

        Args:
            html_content: HTML att parsa

        Returns:
            Parsad information
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Hitta huvudinnehåll
        main = soup.find(["main", "div"], class_=["main", "content", "documentation"])
        if not main:
            main = soup

        # Extrahera information
        info = {
            "title": self._extract_title(main),
            "description": self._extract_description(main),
            "sections": self._extract_sections(main),
        }

        return info

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extraherar titel"""
        title_elem = soup.find(["h1", "h2"], class_=["title", "heading"])
        if title_elem:
            return title_elem.text.strip()

        # Försök hitta första rubriken
        heading = soup.find(["h1", "h2"])
        if heading:
            return heading.text.strip()

        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extraherar beskrivning"""
        desc_elem = soup.find(["p", "div"], class_=["description", "intro"])
        if desc_elem:
            return desc_elem.text.strip()

        # Försök hitta första stycket
        first_p = soup.find("p")
        if first_p:
            return first_p.text.strip()

        return ""

    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar sektioner"""
        sections = []

        # Hitta alla sektioner
        for section in soup.find_all(["section", "div"], class_=["section", "endpoint", "method"]):
            section_info = self._parse_section(section)
            if section_info:
                sections.append(section_info)

        return sections

    def _parse_section(self, section: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parsar en sektion"""
        try:
            # Hitta titel
            title = self._extract_title(section) or section.get("id", "")
            if not title:
                return None

            # Skapa sektion
            section_info = {
                "title": title,
                "description": self._extract_description(section),
                "endpoints": self._extract_endpoints(section),
                "examples": self._extract_examples(section),
                "parameters": self._extract_parameters(section),
            }

            # Ta bort tomma listor
            section_info = {k: v for k, v in section_info.items() if v}

            return section_info

        except Exception as e:
            logger.error(f"Fel vid parsning av sektion: {str(e)}")
            return None

    def _extract_endpoints(self, section: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar endpoints"""
        endpoints = []

        # Hitta alla endpoint-element
        for endpoint in section.find_all(["div", "section"], class_=["endpoint", "method"]):
            try:
                # Hitta metod och sökväg
                method = None
                path = None

                # Sök i olika format
                method_elem = endpoint.find(["span", "code"], class_=["method", "http-method"])
                if method_elem:
                    method = method_elem.text.strip().upper()
                else:
                    # Försök hitta i text
                    text = endpoint.get_text()
                    methods = ["GET", "POST", "PUT", "DELETE"]
                    for m in methods:
                        if m in text:
                            method = m
                            break

                path_elem = endpoint.find(["span", "code"], class_=["path", "endpoint", "url"])
                if path_elem:
                    path = path_elem.text.strip()
                else:
                    # Försök hitta URL-mönster
                    text = endpoint.get_text()
                    urls = re.findall(r'/v[0-9]/[^\s"\']+', text)
                    if urls:
                        path = urls[0]

                if not method or not path:
                    continue

                # Skapa endpoint
                endpoint_info = {
                    "method": method,
                    "path": path,
                    "description": self._extract_description(endpoint),
                    "authentication": self._check_authentication(endpoint),
                    "parameters": self._extract_parameters(endpoint),
                    "response": self._extract_response(endpoint),
                }

                endpoints.append(endpoint_info)

            except Exception as e:
                logger.error(f"Fel vid extrahering av endpoint: {str(e)}")
                continue

        return endpoints

    def _check_authentication(self, element: BeautifulSoup) -> bool:
        """Kontrollerar om autentisering krävs"""
        # Kontrollera text
        text = element.get_text().lower()
        auth_words = ["authenticated", "requires auth", "authorization required"]

        return any(word in text for word in auth_words)

    def _extract_parameters(self, element: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar parametrar"""
        parameters = []

        # Hitta parametertabell eller lista
        param_section = element.find(
            ["table", "div", "ul"], class_=["parameters", "params", "arguments"]
        )
        if not param_section:
            return parameters

        # Hitta alla parametrar
        for param in param_section.find_all(["tr", "li", "div"], class_=["parameter", "argument"]):
            try:
                param_info = {
                    "name": "",
                    "type": "",
                    "required": False,
                    "description": "",
                    "default": None,
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

                if param_info["name"]:
                    parameters.append(param_info)

            except Exception as e:
                logger.error(f"Fel vid extrahering av parameter: {str(e)}")
                continue

        return parameters

    def _extract_response(self, element: BeautifulSoup) -> Dict[str, Any]:
        """Extraherar svarsinformation"""
        response = {"type": "", "description": "", "schema": {}, "examples": []}

        # Hitta svarssektion
        response_section = element.find(
            ["div", "section"], class_=["response", "returns", "result"]
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

    def _extract_examples(self, element: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar exempel"""
        examples = []

        # Hitta alla exempel
        for example in element.find_all(["div", "section"], class_=["example", "sample"]):
            try:
                example_info = {
                    "title": self._extract_title(example),
                    "description": self._extract_description(example),
                    "code": [],
                }

                # Hitta kodexempel
                for code in example.find_all(["pre", "code"]):
                    try:
                        code_text = code.text.strip()
                        if code_text:
                            # Försök parsa som JSON
                            try:
                                code_info = json.loads(code_text)
                            except json.JSONDecodeError:
                                code_info = code_text

                            example_info["code"].append(code_info)
                    except Exception as e:
                        logger.error(f"Fel vid extrahering av kod: {str(e)}")
                        continue

                if example_info["code"]:
                    examples.append(example_info)

            except Exception as e:
                logger.error(f"Fel vid extrahering av exempel: {str(e)}")
                continue

        return examples

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
                # Parsa HTML
                parsed = self.parse_html(data["html"])
            else:
                # Använd data direkt
                parsed = data

            # Spara parsad information
            output_path = self.output_dir / f"{file_path.stem}_parsed.json"
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            logger.info(f"Sparade parsad information till {output_path}")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def process_all_files(self) -> None:
        """Bearbetar alla filer"""
        try:
            # Rensa output-katalog
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True)

            # Bearbeta alla JSON-filer
            for file_path in self.input_dir.glob("*.json"):
                if file_path.name != "index.json":
                    self.process_file(file_path)

            logger.info("HTML-parsning slutförd!")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {str(e)}")


def main():
    parser = BitfinexHtmlParser()
    parser.process_all_files()


if __name__ == "__main__":
    main()

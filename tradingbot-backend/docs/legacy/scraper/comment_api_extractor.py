import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

from bs4 import BeautifulSoup, Comment

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CommentApiExtractor:
    def __init__(self, input_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar API-extraktor för kommentarer

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
        Extraherar API-information från HTML-kommentarer

        Args:
            html_content: HTML att analysera

        Returns:
            Lista med API-information
        """
        soup = BeautifulSoup(html_content, "html.parser")
        api_info = []

        # Hitta alla kommentarer
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            # Kontrollera om kommentaren innehåller API-information
            if any(
                word in comment.string.lower() for word in ["api", "endpoint", "method"]
            ):
                # Extrahera endpoints från kommentaren
                endpoints = self._extract_endpoints_from_comment(comment.string)
                api_info.extend(endpoints)

        return api_info

    def _extract_endpoints_from_comment(self, comment: str) -> List[Dict[str, Any]]:
        """
        Extraherar endpoints från en kommentar

        Args:
            comment: Kommentar att analysera

        Returns:
            Lista med endpoints
        """
        endpoints = []

        # Dela upp i rader
        lines = comment.split("\n")
        current_endpoint = None

        for line in lines:
            line = line.strip()

            # Kontrollera om raden innehåller en metod och sökväg
            method_match = re.match(r"^(GET|POST|PUT|DELETE)\s+(/[^\s]+)", line)
            if method_match:
                # Spara föregående endpoint om den finns
                if current_endpoint:
                    endpoints.append(current_endpoint)

                # Skapa ny endpoint
                current_endpoint = {
                    "method": method_match.group(1),
                    "path": method_match.group(2),
                    "description": "",
                    "authentication": False,
                    "parameters": [],
                    "response": {
                        "type": "",
                        "description": "",
                        "schema": {},
                        "examples": [],
                    },
                    "examples": [],
                }

                # Extrahera beskrivning från resten av raden
                description = line[method_match.end() :].strip()
                if description:
                    current_endpoint["description"] = description

            elif current_endpoint:
                # Kontrollera om raden innehåller parametrar
                param_match = re.match(r"@param\s+(\w+)\s+(\{[^}]+\})?\s*(.+)", line)
                if param_match:
                    param_name = param_match.group(1)
                    param_type = param_match.group(2) or ""
                    param_desc = param_match.group(3)

                    # Rensa parametertyp
                    param_type = param_type.strip("{}") if param_type else ""

                    # Kontrollera om obligatorisk
                    required = (
                        "required" in param_desc.lower()
                        and "optional" not in param_desc.lower()
                    )

                    current_endpoint["parameters"].append(
                        {
                            "name": param_name,
                            "type": param_type,
                            "required": required,
                            "description": param_desc,
                        }
                    )

                # Kontrollera om raden innehåller svarsinformation
                elif "@return" in line or "@response" in line:
                    response_text = (
                        line.split("@return")[-1].split("@response")[-1].strip()
                    )
                    current_endpoint["response"]["description"] = response_text

                # Kontrollera om raden innehåller autentiseringskrav
                elif "@auth" in line or "@authentication" in line:
                    current_endpoint["authentication"] = True

                # Kontrollera om raden innehåller exempel
                elif "@example" in line:
                    example_lines = []
                    example_started = False

                # Annars lägg till i beskrivningen
                elif line and not line.startswith("@"):
                    if current_endpoint["description"]:
                        current_endpoint["description"] += " "
                    current_endpoint["description"] += line

        # Lägg till sista endpoint
        if current_endpoint:
            endpoints.append(current_endpoint)

        return endpoints

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
    extractor = CommentApiExtractor()
    extractor.process_all_files()


if __name__ == "__main__":
    main()

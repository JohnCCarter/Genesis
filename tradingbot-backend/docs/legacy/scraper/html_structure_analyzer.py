import html
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HtmlStructureAnalyzer:
    def __init__(self, input_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar HTML-strukturanalyserare

        Args:
            input_dir: Sökväg till input-katalogen
        """
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir / "analysis"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyserar HTML-struktur

        Args:
            html_content: HTML att analysera

        Returns:
            Analysresultat
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Samla information
        analysis = {
            "title": self._get_title(soup),
            "metadata": self._get_metadata(soup),
            "structure": self._analyze_structure(soup),
            "classes": self._get_classes(soup),
            "code_blocks": self._analyze_code_blocks(soup),
            "links": self._analyze_links(soup),
            "api_info": self._find_api_info(soup),
        }

        return analysis

    def _get_title(self, soup: BeautifulSoup) -> str:
        """Hämtar titel"""
        title = ""

        # Hitta titel
        title_elem = soup.find("title")
        if title_elem:
            title = title_elem.text.strip()

        return title

    def _get_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Hämtar metadata"""
        metadata = {}

        # Hitta alla meta-taggar
        for meta in soup.find_all("meta"):
            name = meta.get("name", meta.get("property", ""))
            content = meta.get("content", "")
            if name and content:
                metadata[name] = content

        return metadata

    def _analyze_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyserar HTML-struktur"""
        structure = {
            "headings": self._analyze_headings(soup),
            "sections": self._analyze_sections(soup),
            "tables": self._analyze_tables(soup),
        }

        return structure

    def _analyze_headings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyserar rubriker"""
        headings = []

        # Hitta alla rubriker
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for heading in soup.find_all(tag):
                heading_info = {
                    "level": int(tag[1]),
                    "text": heading.text.strip(),
                    "id": heading.get("id", ""),
                    "classes": heading.get("class", []),
                }
                headings.append(heading_info)

        return headings

    def _analyze_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyserar sektioner"""
        sections = []

        # Hitta alla sektioner
        for section in soup.find_all(["div", "section"]):
            section_info = {
                "tag": section.name,
                "id": section.get("id", ""),
                "classes": section.get("class", []),
                "content_type": self._guess_content_type(section),
            }
            sections.append(section_info)

        return sections

    def _analyze_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyserar tabeller"""
        tables = []

        # Hitta alla tabeller
        for table in soup.find_all("table"):
            # Hitta rubrikrad
            headers = []
            header_row = table.find("tr")
            if header_row:
                for th in header_row.find_all(["th", "td"]):
                    headers.append(th.text.strip())

            table_info = {
                "headers": headers,
                "classes": table.get("class", []),
                "rows": (
                    len(table.find_all("tr")) - 1
                    if headers
                    else len(table.find_all("tr"))
                ),
            }
            tables.append(table_info)

        return tables

    def _get_classes(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Hämtar alla CSS-klasser"""
        classes = {}

        # Hitta alla element med klasser
        for element in soup.find_all(class_=True):
            for class_name in element.get("class", []):
                classes[class_name] = classes.get(class_name, 0) + 1

        return classes

    def _analyze_code_blocks(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyserar kodblock"""
        code_blocks = []

        # Hitta alla kodblock
        for block in soup.find_all(["pre", "code"]):
            code_text = block.get_text()

            code_info = {
                "tag": block.name,
                "classes": block.get("class", []),
                "language": self._guess_language(code_text),
                "content_type": self._guess_content_type(block),
                "length": len(code_text),
            }
            code_blocks.append(code_info)

        return code_blocks

    def _analyze_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyserar länkar"""
        links = []

        # Hitta alla länkar
        for link in soup.find_all("a"):
            href = link.get("href", "")
            if href:
                link_info = {
                    "text": link.text.strip(),
                    "href": href,
                    "classes": link.get("class", []),
                    "type": self._guess_link_type(href),
                }
                links.append(link_info)

        return links

    def _find_api_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Hittar API-information"""
        api_info = {
            "potential_endpoints": [],
            "potential_parameters": [],
            "potential_examples": [],
        }

        # Hitta potentiella endpoints
        for element in soup.find_all(
            string=re.compile(r"(GET|POST|PUT|DELETE)\s+/[^\s]+")
        ):
            api_info["potential_endpoints"].append(
                {
                    "text": element.strip(),
                    "parent_tag": element.parent.name,
                    "parent_classes": element.parent.get("class", []),
                }
            )

        # Hitta potentiella parametrar
        for element in soup.find_all(["td", "th", "dt", "strong"]):
            text = element.text.strip()
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", text):
                next_elem = element.find_next_sibling()
                if next_elem:
                    api_info["potential_parameters"].append(
                        {
                            "name": text,
                            "description": next_elem.text.strip(),
                            "parent_tag": element.parent.name,
                            "parent_classes": element.parent.get("class", []),
                        }
                    )

        # Hitta potentiella exempel
        for block in soup.find_all(["pre", "code"]):
            code_text = block.get_text()
            if any(word in code_text.lower() for word in ["curl", "http", "request"]):
                api_info["potential_examples"].append(
                    {
                        "text": code_text,
                        "classes": block.get("class", []),
                        "parent_tag": block.parent.name,
                        "parent_classes": block.parent.get("class", []),
                    }
                )

        return api_info

    def _guess_language(self, code: str) -> str:
        """Gissar programmeringsspråk"""
        # Enkla regler för att gissa språk
        if re.search(r"curl\s+-X", code):
            return "shell"
        elif "{" in code and "}" in code:
            return "json"
        elif re.search(r"function\s+\w+\s*\(", code):
            return "javascript"
        elif re.search(r"def\s+\w+\s*\(", code):
            return "python"
        else:
            return "unknown"

    def _guess_content_type(self, element: BeautifulSoup) -> str:
        """Gissar innehållstyp"""
        text = element.get_text()

        if re.search(r"(GET|POST|PUT|DELETE)\s+/[^\s]+", text):
            return "api"
        elif re.search(r"curl\s+-X", text):
            return "example"
        elif "{" in text and "}" in text:
            return "json"
        elif re.search(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*[:-]", text):
            return "parameter"
        else:
            return "text"

    def _guess_link_type(self, href: str) -> str:
        """Gissar länktyp"""
        if href.startswith("#"):
            return "anchor"
        elif href.startswith("http"):
            return "external"
        else:
            return "internal"

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
                # Analysera HTML
                analysis = self.analyze_html(data["html"])

                # Spara analys
                output_path = self.output_dir / f"{file_path.stem}_analysis.json"
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(analysis, f, indent=2, ensure_ascii=False)

                logger.info(f"Sparade analys till {output_path}")
            else:
                logger.warning(f"Ingen HTML hittades i {file_path}")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def process_all_files(self) -> None:
        """Bearbetar alla filer"""
        try:
            # Rensa output-katalog
            if self.output_dir.exists():
                for file in self.output_dir.glob("*.json"):
                    file.unlink()
            else:
                self.output_dir.mkdir(parents=True)

            # Bearbeta alla filer
            for file_path in self.input_dir.glob("*.json"):
                self.process_file(file_path)

            logger.info("HTML-analys slutförd!")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {str(e)}")


def main():
    analyzer = HtmlStructureAnalyzer()
    analyzer.process_all_files()


if __name__ == "__main__":
    main()

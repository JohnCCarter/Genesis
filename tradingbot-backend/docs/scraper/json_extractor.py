import html
import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class JsonExtractor:
    def __init__(self, cache_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar JSON-extraktorn

        Args:
            cache_dir: Sökväg till cache-katalogen med scrapade filer
        """
        self.cache_dir = cache_dir
        self.output_dir = os.path.join(cache_dir, "extracted")
        os.makedirs(self.output_dir, exist_ok=True)

    def clean_text(self, text: str) -> str:
        """
        Rensar text från whitespace och HTML-entities

        Args:
            text: Text att rensa

        Returns:
            Rensad text
        """
        # Avkoda HTML-entities först
        text = html.unescape(text)

        # Ta bort onödig whitespace men behåll struktur
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        return " ".join(lines)

    def extract_balanced_json(self, text: str, start: int = 0) -> Optional[Tuple[str, int]]:
        """
        Extraherar ett balanserat JSON-objekt eller array från text

        Args:
            text: Text att extrahera från
            start: Startposition

        Returns:
            Tuple med extraherad JSON-sträng och slutposition, eller None om inget hittades
        """
        # Hitta start av JSON-objekt eller array
        while start < len(text):
            if text[start] in "{[":
                break
            start += 1
        else:
            return None

        # Matcha klammerparenteser/hakparenteser
        opening = text[start]
        closing = "}" if opening == "{" else "]"
        count = 1
        pos = start + 1
        in_string = False
        escape = False

        while pos < len(text) and count > 0:
            char = text[pos]

            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if char == opening:
                    count += 1
                elif char == closing:
                    count -= 1

            pos += 1

        if count == 0:
            return text[start:pos], pos
        return None

    def is_valid_json_content(self, obj: Any) -> bool:
        """
        Kontrollerar om ett JSON-objekt innehåller meningsfull data

        Args:
            obj: Objektet att kontrollera

        Returns:
            True om objektet är giltigt, False annars
        """
        if isinstance(obj, dict):
            # Kontrollera att objektet har minst en nyckel
            return len(obj) > 0
        elif isinstance(obj, list):
            # Kontrollera att arrayen har element och inte bara är nummer
            return len(obj) > 0 and not all(isinstance(x, (int, float)) for x in obj)
        return False

    def find_json_objects(self, text: str) -> List[Union[Dict[str, Any], List[Any]]]:
        """
        Hittar alla JSON-objekt och arrays i en text

        Args:
            text: Text att söka i

        Returns:
            Lista med JSON-objekt och arrays
        """
        json_objects = []
        pos = 0

        while pos < len(text):
            result = self.extract_balanced_json(text, pos)
            if not result:
                break

            json_str, next_pos = result
            try:
                # Ersätt dubbla citattecken med enkla
                json_str = json_str.replace('""', '"')
                json_obj = json.loads(json_str)

                # Kontrollera att objektet är meningsfullt
                if self.is_valid_json_content(json_obj):
                    json_objects.append(json_obj)
                else:
                    logger.debug(f"Skipping non-meaningful JSON: {json_str[:100]}...")

            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON: {str(e)}")

            pos = next_pos

        return json_objects

    def extract_json_from_html(self, html_content: str) -> List[Union[Dict[str, Any], List[Any]]]:
        """
        Extraherar JSON-objekt och arrays från HTML-innehåll

        Args:
            html_content: HTML-innehållet att analysera

        Returns:
            Lista med extraherade JSON-objekt och arrays
        """
        soup = BeautifulSoup(html_content, "html.parser")
        json_objects = []

        # Hitta alla script-taggar och pre-taggar
        for element in soup.find_all(["script", "pre"]):
            if element.string:
                # Rensa texten
                cleaned_text = self.clean_text(element.string)
                # Hitta JSON-objekt och arrays
                objects = self.find_json_objects(cleaned_text)
                json_objects.extend(objects)

        return json_objects

    def save_json(self, json_obj: Union[Dict[str, Any], List[Any]], filename: str) -> None:
        """
        Sparar JSON-objekt eller array till fil

        Args:
            json_obj: JSON-objektet eller arrayen att spara
            filename: Filnamn att spara som
        """
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON to {output_path}")

    def process_file(self, filename: str) -> Optional[List[Union[Dict[str, Any], List[Any]]]]:
        """
        Bearbetar en enskild fil

        Args:
            filename: Filnamn att bearbeta

        Returns:
            Lista med extraherade JSON-objekt och arrays eller None vid fel
        """
        try:
            file_path = os.path.join(self.cache_dir, filename)
            logger.info(f"Processing file: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Om filen är en JSON-fil, försök läsa den direkt
            if filename.endswith(".json"):
                try:
                    json_obj = json.loads(content)
                    if self.is_valid_json_content(json_obj):
                        logger.info(f"Found valid JSON in {filename}")
                        # Spara i extracted-katalogen med samma namn
                        self.save_json(json_obj, filename)
                        return [json_obj]
                    else:
                        logger.info(f"Skipping non-meaningful JSON in {filename}")
                        return None
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON file {filename}: {str(e)}")
                    # Försök extrahera JSON från innehållet som HTML
                    logger.info("Trying to extract JSON from file content...")

            # Om det inte är en JSON-fil eller om JSON-parsning misslyckades
            json_objects = self.extract_json_from_html(content)

            if json_objects:
                logger.info(f"Found {len(json_objects)} JSON objects/arrays in {filename}")
                # Spara varje JSON-objekt/array separat
                for i, obj in enumerate(json_objects):
                    base_name = os.path.splitext(filename)[0]
                    if len(json_objects) > 1:
                        json_filename = f"{base_name}_{i+1}.json"
                    else:
                        json_filename = f"{base_name}.json"
                    self.save_json(obj, json_filename)

            return json_objects

        except Exception as e:
            logger.error(f"Error processing {filename}: {str(e)}")
            return None

    def process_all_files(self) -> Dict[str, List[Union[Dict[str, Any], List[Any]]]]:
        """
        Bearbetar alla filer i cache-katalogen

        Returns:
            Dictionary med filnamn som nycklar och extraherade JSON-objekt/arrays som värden
        """
        results = {}

        for filename in os.listdir(self.cache_dir):
            if filename == "extracted":  # Hoppa över extracted-katalogen
                continue

            json_objects = self.process_file(filename)
            if json_objects:
                results[filename] = json_objects

        return results

    def cleanup(self):
        """Rensar extracted-katalogen"""
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
            logger.info(f"Cleaned up {self.output_dir}")


def main():
    extractor = JsonExtractor()
    results = extractor.process_all_files()

    # Skriv ut sammanfattning
    print("\nBearbetning slutförd!")
    print(f"Bearbetade {len(results)} filer")
    for filename, objects in results.items():
        print(f"- {filename}: {len(objects)} JSON-objekt/arrays extraherade")


if __name__ == "__main__":
    main()

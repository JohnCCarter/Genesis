import os
import json
import html
import shutil
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
import re

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JsonFinder:
    def __init__(self, input_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar JSON-hittare
        
        Args:
            input_dir: Sökväg till input-katalogen
        """
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir / "json"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def find_json_in_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Hittar JSON-objekt i text
        
        Args:
            text: Text att söka i
            
        Returns:
            Lista med JSON-objekt
        """
        json_objects = []
        start = 0
        
        while True:
            # Hitta början av ett potentiellt JSON-objekt
            start = text.find('{', start)
            if start == -1:
                break
                
            # Hitta matchande slutparentes
            count = 1
            pos = start + 1
            in_string = False
            escape = False
            
            while pos < len(text) and count > 0:
                char = text[pos]
                
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        count += 1
                    elif char == '}':
                        count -= 1
                        
                pos += 1
                
            if count == 0:
                try:
                    json_str = text[start:pos]
                    json_obj = json.loads(json_str)
                    if isinstance(json_obj, dict):
                        json_objects.append(json_obj)
                except json.JSONDecodeError:
                    pass
                    
            start = pos
            
        return json_objects

    def find_json_in_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Hittar JSON-objekt i HTML
        
        Args:
            html_content: HTML att söka i
            
        Returns:
            Lista med JSON-objekt
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        json_objects = []
        
        # Hitta alla script-taggar med JSON
        for script in soup.find_all('script'):
            if script.string:
                # Avkoda HTML-entities
                text = html.unescape(script.string)
                
                # Hitta JSON-objekt i texten
                objects = self.find_json_in_text(text)
                json_objects.extend(objects)
                
        # Hitta alla data-attribut som kan innehålla JSON
        for element in soup.find_all(attrs={"data-initial-props": True}):
            try:
                data_str = html.unescape(element["data-initial-props"])
                data = json.loads(data_str)
                if isinstance(data, dict):
                    json_objects.append(data)
            except (json.JSONDecodeError, KeyError):
                pass
                
        # Hitta alla pre/code-taggar som kan innehålla JSON
        for code in soup.find_all(['pre', 'code']):
            if code.string:
                text = html.unescape(code.string)
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        json_objects.append(data)
                except json.JSONDecodeError:
                    # Om det inte är ren JSON, leta efter JSON-objekt i texten
                    objects = self.find_json_in_text(text)
                    json_objects.extend(objects)
                    
        return json_objects

    def is_api_related(self, obj: Dict[str, Any]) -> bool:
        """
        Kontrollerar om ett objekt är API-relaterat
        
        Args:
            obj: Objekt att kontrollera
            
        Returns:
            True om objektet är API-relaterat
        """
        # Kontrollera nycklar som indikerar API-information
        api_keys = [
            'method', 'path', 'endpoint', 'url',
            'parameters', 'params', 'args',
            'response', 'returns', 'result',
            'authentication', 'auth', 'authenticated'
        ]
        
        return any(key in obj for key in api_keys)

    def is_schema_related(self, obj: Dict[str, Any]) -> bool:
        """
        Kontrollerar om ett objekt är schema-relaterat
        
        Args:
            obj: Objekt att kontrollera
            
        Returns:
            True om objektet är schema-relaterat
        """
        # Kontrollera nycklar som indikerar schema-information
        schema_keys = [
            'type', 'properties', 'required',
            'items', 'schema', 'definitions'
        ]
        
        return any(key in obj for key in schema_keys)

    def categorize_object(self, obj: Dict[str, Any]) -> str:
        """
        Kategoriserar ett objekt
        
        Args:
            obj: Objekt att kategorisera
            
        Returns:
            Kategori för objektet
        """
        if self.is_api_related(obj):
            return 'api'
        elif self.is_schema_related(obj):
            return 'schema'
        else:
            return 'other'

    def process_file(self, file_path: Path) -> None:
        """
        Bearbetar en fil
        
        Args:
            file_path: Sökväg till filen
        """
        try:
            logger.info(f"Bearbetar {file_path}")
            
            # Läs fil
            with file_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Kontrollera om det är ett HTML-dokument
            if isinstance(data, dict) and 'html' in data:
                # Hitta JSON i HTML
                objects = self.find_json_in_html(data['html'])
            else:
                # Använd data direkt
                objects = [data]
                
            # Kategorisera och spara objekt
            for i, obj in enumerate(objects):
                category = self.categorize_object(obj)
                
                # Skapa filnamn
                if len(objects) > 1:
                    filename = f"{file_path.stem}_{i+1}.json"
                else:
                    filename = f"{file_path.stem}.json"
                    
                # Skapa kategori-katalog
                category_dir = self.output_dir / category
                category_dir.mkdir(exist_ok=True)
                
                # Spara objekt
                output_path = category_dir / filename
                with output_path.open('w', encoding='utf-8') as f:
                    json.dump(obj, f, indent=2, ensure_ascii=False)
                    
                logger.info(f"Sparade {category}/{filename}")
                
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def create_index(self) -> None:
        """Skapar en index-fil"""
        index = {
            "title": "Bitfinex API Documentation",
            "description": "Extraherad JSON-data från Bitfinex-dokumentation",
            "categories": {}
        }
        
        # Samla information från alla kategorier
        for category_dir in self.output_dir.glob("*"):
            if not category_dir.is_dir():
                continue
                
            category = category_dir.name
            files = []
            
            for file in category_dir.glob("*.json"):
                try:
                    with file.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    files.append({
                        "name": file.stem,
                        "file": file.name,
                        "size": file.stat().st_size,
                        "keys": list(data.keys()) if isinstance(data, dict) else []
                    })
                except Exception as e:
                    logger.error(f"Fel vid indexering av {file}: {str(e)}")
                    
            if files:
                index["categories"][category] = {
                    "count": len(files),
                    "files": sorted(files, key=lambda x: x["name"])
                }
                
        # Spara index
        with (self.output_dir / "index.json").open('w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
        logger.info("Skapade index.json")

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
                    
            # Skapa index
            self.create_index()
            
            logger.info("JSON-extrahering slutförd!")
            
        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {str(e)}")

def main():
    finder = JsonFinder()
    finder.process_all_files()

if __name__ == '__main__':
    main()

import os
import json
import html
import shutil
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional, Union, Iterator
from dataclasses import dataclass
from pathlib import Path
import logging

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ApiEndpoint:
    """Representerar en API-endpoint"""
    method: str
    path: str
    description: str
    parameters: List[Dict[str, Any]]
    response: Dict[str, Any]
    authentication: bool
    rate_limit: Optional[str] = None

@dataclass
class ApiSection:
    """Representerar en sektion av API-dokumentationen"""
    title: str
    description: str
    endpoints: List[ApiEndpoint]

class EnhancedJsonExtractor:
    def __init__(self, cache_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar JSON-extraktorn med förbättrad funktionalitet
        
        Args:
            cache_dir: Sökväg till cache-katalogen
        """
        self.cache_dir = Path(cache_dir)
        self.output_dir = self.cache_dir / "extracted"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Skapa undermappar för olika typer av innehåll
        self.docs_dir = self.output_dir / "docs"
        self.endpoints_dir = self.output_dir / "endpoints"
        self.schemas_dir = self.output_dir / "schemas"
        
        for dir in [self.docs_dir, self.endpoints_dir, self.schemas_dir]:
            dir.mkdir(exist_ok=True)

    def read_file_chunks(self, file_path: Path, chunk_size: int = 8192) -> str:
        """
        Läser en fil i chunks för att hantera stora filer
        
        Args:
            file_path: Sökväg till filen
            chunk_size: Storlek på varje chunk i bytes
            
        Returns:
            Filens innehåll
        """
        content = []
        with file_path.open('r', encoding='utf-8') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                content.append(chunk)
        return ''.join(content)

    def extract_json_from_html(self, content: str) -> List[Dict[str, Any]]:
        """
        Extraherar JSON från HTML eller ren JSON
        
        Args:
            content: Innehåll att analysera
            
        Returns:
            Lista med extraherade JSON-objekt
        """
        # Försök först tolka som ren JSON
        try:
            data = json.loads(content)
            if isinstance(data, (dict, list)):
                return [data]
        except json.JSONDecodeError:
            pass

        # Om det inte är ren JSON, försök extrahera från HTML
        soup = BeautifulSoup(content, 'html.parser')
        json_objects = []

        # Hitta alla script-taggar med JSON
        for script in soup.find_all(['script', 'pre', 'code']):
            if not script.string:
                continue
                
            # Rensa och avkoda innehållet
            text = html.unescape(script.string.strip())
            
            # Hitta alla JSON-objekt i texten
            start = 0
            while start < len(text):
                # Hitta start av JSON
                json_start = text.find('{', start)
                array_start = text.find('[', start)
                
                if json_start == -1 and array_start == -1:
                    break
                    
                # Välj den första förekomsten av { eller [
                if json_start == -1:
                    start = array_start
                    end_char = ']'
                elif array_start == -1:
                    start = json_start
                    end_char = '}'
                else:
                    if json_start < array_start:
                        start = json_start
                        end_char = '}'
                    else:
                        start = array_start
                        end_char = ']'
                
                # Hitta matchande slutparentes
                count = 1
                pos = start + 1
                while pos < len(text) and count > 0:
                    if text[pos] == '{' if end_char == '}' else '[':
                        count += 1
                    elif text[pos] == end_char:
                        count -= 1
                    pos += 1
                
                if count == 0:
                    try:
                        json_str = text[start:pos]
                        json_obj = json.loads(json_str)
                        if isinstance(json_obj, (dict, list)):
                            json_objects.append(json_obj)
                    except json.JSONDecodeError:
                        pass
                
                start = pos

        return json_objects

    def categorize_content(self, data: Any) -> str:
        """
        Kategoriserar innehåll baserat på struktur och nyckelord
        
        Args:
            data: Data att kategorisera
            
        Returns:
            Kategori (docs, endpoints, schemas)
        """
        if isinstance(data, dict):
            # Kontrollera om det är API-dokumentation
            if any(key in data for key in ['method', 'path', 'endpoints', 'parameters']):
                return 'endpoints'
            # Kontrollera om det är ett schema
            elif any(key in data for key in ['type', 'properties', 'required']):
                return 'schemas'
            # Annars är det generell dokumentation
            return 'docs'
        elif isinstance(data, list):
            # Om listan innehåller objekt, kolla första objektet
            if data and isinstance(data[0], dict):
                return self.categorize_content(data[0])
        return 'docs'

    def format_content(self, data: Any, category: str) -> Dict[str, Any]:
        """
        Formaterar innehåll baserat på kategori
        
        Args:
            data: Data att formatera
            category: Innehållets kategori
            
        Returns:
            Formaterad data
        """
        if category == 'endpoints':
            return self._format_endpoint(data)
        elif category == 'schemas':
            return self._format_schema(data)
        else:
            return self._format_doc(data)

    def _format_endpoint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Formaterar API-endpoint dokumentation"""
        formatted = {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "method": data.get("method", ""),
            "path": data.get("path", ""),
            "authentication": data.get("authentication", False),
            "parameters": [],
            "response": {},
            "examples": []
        }
        
        # Formatera parametrar
        if "parameters" in data:
            for param in data["parameters"]:
                formatted["parameters"].append({
                    "name": param.get("name", ""),
                    "type": param.get("type", ""),
                    "required": param.get("required", False),
                    "description": param.get("description", ""),
                    "default": param.get("default", None)
                })
                
        # Formatera svar
        if "response" in data:
            formatted["response"] = {
                "type": data["response"].get("type", ""),
                "description": data["response"].get("description", ""),
                "schema": data["response"].get("schema", {}),
                "examples": data["response"].get("examples", [])
            }
            
        return formatted

    def _format_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Formaterar schema-dokumentation"""
        return {
            "title": data.get("title", ""),
            "type": data.get("type", "object"),
            "description": data.get("description", ""),
            "properties": data.get("properties", {}),
            "required": data.get("required", []),
            "examples": data.get("examples", [])
        }

    def _format_doc(self, data: Any) -> Dict[str, Any]:
        """Formaterar generell dokumentation"""
        if isinstance(data, dict):
            return {
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "content": data
            }
        elif isinstance(data, list):
            return {
                "title": "Collection",
                "description": "",
                "items": data
            }
        else:
            return {
                "title": "Document",
                "description": "",
                "content": str(data)
            }

    def save_json(self, data: Any, filename: str, category: str) -> None:
        """
        Sparar JSON-data i rätt kategori
        
        Args:
            data: Data att spara
            filename: Filnamn
            category: Kategori (docs, endpoints, schemas)
        """
        if category == "docs":
            output_dir = self.docs_dir
        elif category == "endpoints":
            output_dir = self.endpoints_dir
        else:
            output_dir = self.schemas_dir
            
        output_path = output_dir / filename
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Sparade {category}/{filename}")

    def create_index(self) -> None:
        """Skapar en index-fil för all dokumentation"""
        index = {
            "docs": [],
            "endpoints": [],
            "schemas": []
        }
        
        # Samla information från alla kategorier
        for category in ["docs", "endpoints", "schemas"]:
            dir_path = getattr(self, f"{category}_dir")
            if not dir_path.exists():
                continue
                
            for file_path in dir_path.glob("*.json"):
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    index[category].append({
                        "file": file_path.name,
                        "title": data.get("title", file_path.stem),
                        "description": data.get("description", "")
                    })
                except Exception as e:
                    logger.error(f"Fel vid indexering av {file_path}: {e}")
                    
        # Spara index
        index_path = self.output_dir / "index.json"
        with index_path.open('w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
        logger.info("Skapade index.json")

    def process_file(self, file_path: Path) -> None:
        """
        Bearbetar en fil och extraherar/formaterar innehållet
        
        Args:
            file_path: Sökväg till filen
        """
        try:
            logger.info(f"Bearbetar {file_path}")
            
            # Läs filinnehåll
            content = self.read_file_chunks(file_path)
            
            # Extrahera JSON
            json_objects = self.extract_json_from_html(content)
            
            if not json_objects:
                logger.warning(f"Inga JSON-objekt hittades i {file_path}")
                return
                
            # Bearbeta varje objekt
            for i, obj in enumerate(json_objects):
                # Kategorisera innehållet
                category = self.categorize_content(obj)
                
                # Formatera innehållet
                formatted = self.format_content(obj, category)
                
                # Skapa filnamn
                base_name = file_path.stem
                if len(json_objects) > 1:
                    filename = f"{base_name}_{i+1}.json"
                else:
                    filename = f"{base_name}.json"
                    
                # Spara formaterad JSON
                self.save_json(formatted, filename, category)
                
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {e}")

    def process_all_files(self) -> None:
        """Bearbetar alla filer i cache-katalogen"""
        try:
            # Rensa output-kataloger
            for dir in [self.docs_dir, self.endpoints_dir, self.schemas_dir]:
                if dir.exists():
                    shutil.rmtree(dir)
                dir.mkdir(parents=True)
            
            # Bearbeta alla filer
            for file_path in self.cache_dir.glob("*.json"):
                if file_path.name != "index.json":
                    self.process_file(file_path)
                    
            # Skapa index
            self.create_index()
            
            logger.info("Bearbetning slutförd!")
            
        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {e}")

def main():
    extractor = EnhancedJsonExtractor()
    extractor.process_all_files()

if __name__ == "__main__":
    main()
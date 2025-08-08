import os
import json
import html
import shutil
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
import logging
import re

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BitfinexDocsParser:
    def __init__(self, cache_dir: str = "cache/bitfinex_docs"):
        """
        Initialiserar dokumentationsparser
        
        Args:
            cache_dir: Sökväg till cache-katalogen
        """
        self.cache_dir = Path(cache_dir)
        self.docs_dir = self.cache_dir / "docs"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def read_file_chunks(self, file_path: Path, chunk_size: int = 8192) -> Iterator[str]:
        """
        Läser en fil i chunks
        
        Args:
            file_path: Sökväg till filen
            chunk_size: Storlek på varje chunk
            
        Yields:
            Chunks av filinnehållet
        """
        with file_path.open('r', encoding='utf-8') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def find_json_objects(self, text: str) -> List[Dict[str, Any]]:
        """
        Hittar alla JSON-objekt i en text
        
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

    def extract_api_info(self, json_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extraherar API-information från ett JSON-objekt
        
        Args:
            json_obj: JSON-objekt att analysera
            
        Returns:
            API-information eller None
        """
        # Kontrollera om objektet innehåller API-information
        if not isinstance(json_obj, dict):
            return None
            
        # Hitta relevanta nycklar
        api_keys = [
            'method', 'path', 'endpoint', 'url',
            'parameters', 'params', 'args',
            'response', 'returns', 'result',
            'description', 'doc', 'documentation'
        ]
        
        if not any(key in json_obj for key in api_keys):
            return None
            
        # Extrahera information
        api_info = {
            'method': json_obj.get('method', ''),
            'path': json_obj.get('path', json_obj.get('endpoint', json_obj.get('url', ''))),
            'description': json_obj.get('description', json_obj.get('doc', '')),
            'parameters': [],
            'response': {},
            'authentication': False
        }
        
        # Hantera parametrar
        params = json_obj.get('parameters', json_obj.get('params', json_obj.get('args', [])))
        if isinstance(params, dict):
            params = [{'name': k, **v} for k, v in params.items()]
        elif isinstance(params, list):
            api_info['parameters'] = params
            
        # Hantera svar
        response = json_obj.get('response', json_obj.get('returns', json_obj.get('result', {})))
        if isinstance(response, dict):
            api_info['response'] = response
            
        # Kontrollera autentisering
        auth_keys = ['auth', 'authentication', 'authenticated', 'requires_auth']
        for key in auth_keys:
            if key in json_obj:
                api_info['authentication'] = bool(json_obj[key])
                break
                
        return api_info

    def categorize_content(self, content: Dict[str, Any]) -> str:
        """
        Kategoriserar innehåll baserat på struktur och nyckelord
        
        Args:
            content: Innehåll att kategorisera
            
        Returns:
            Kategorinamn
        """
        # Kontrollera om det är API-dokumentation
        if any(key in content for key in ['method', 'path', 'endpoint', 'url']):
            return 'api'
            
        # Kontrollera om det är schema/modell
        if any(key in content for key in ['type', 'properties', 'required']):
            return 'schema'
            
        # Kontrollera om det är konfiguration
        if any(key in content for key in ['config', 'settings', 'options']):
            return 'config'
            
        # Annars är det generell dokumentation
        return 'general'

    def save_content(self, content: Dict[str, Any], category: str, name: str) -> None:
        """
        Sparar innehåll i rätt kategori
        
        Args:
            content: Innehåll att spara
            category: Innehållets kategori
            name: Filnamn (utan .json)
        """
        # Skapa kategori-katalog
        category_dir = self.docs_dir / category
        category_dir.mkdir(exist_ok=True)
        
        # Spara innehåll
        filepath = category_dir / f"{name}.json"
        with filepath.open('w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Sparade {category}/{name}.json")

    def create_index(self) -> None:
        """Skapar en index-fil för all dokumentation"""
        index = {
            "title": "Bitfinex API Documentation",
            "description": "Strukturerad dokumentation för Bitfinex API",
            "categories": {}
        }
        
        # Samla information från alla kategorier
        for category_dir in self.docs_dir.glob("*"):
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
                        "title": data.get("title", ""),
                        "description": data.get("description", "")
                    })
                except Exception as e:
                    logger.error(f"Fel vid indexering av {file}: {str(e)}")
                    
            if files:
                index["categories"][category] = {
                    "count": len(files),
                    "files": sorted(files, key=lambda x: x["name"])
                }
                
        # Spara index
        with (self.docs_dir / "index.json").open('w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
        logger.info("Skapade docs/index.json")

    def process_file(self, file_path: Path) -> None:
        """
        Bearbetar en fil och extraherar dokumentation
        
        Args:
            file_path: Sökväg till filen
        """
        try:
            logger.info(f"Bearbetar {file_path}")
            
            # Läs fil i chunks
            content = []
            for chunk in self.read_file_chunks(file_path):
                content.append(chunk)
            content = ''.join(content)
            
            # Hitta alla JSON-objekt
            json_objects = self.find_json_objects(content)
            
            if not json_objects:
                logger.warning(f"Inga JSON-objekt hittades i {file_path}")
                return
                
            # Bearbeta varje objekt
            for i, obj in enumerate(json_objects):
                # Extrahera API-information om möjligt
                api_info = self.extract_api_info(obj)
                if api_info:
                    obj = api_info
                    
                # Kategorisera innehåll
                category = self.categorize_content(obj)
                
                # Skapa filnamn
                base_name = file_path.stem
                if len(json_objects) > 1:
                    name = f"{base_name}_{i+1}"
                else:
                    name = base_name
                    
                # Spara innehåll
                self.save_content(obj, category, name)
                
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def process_all_files(self) -> None:
        """Bearbetar alla relevanta filer i cache-katalogen"""
        try:
            # Rensa docs-katalogen
            if self.docs_dir.exists():
                shutil.rmtree(self.docs_dir)
            self.docs_dir.mkdir(parents=True)
            
            # Bearbeta alla JSON-filer
            for file_path in self.cache_dir.glob("*.json"):
                self.process_file(file_path)
                
            # Skapa index
            self.create_index()
            
            logger.info("Dokumentationsextrahering slutförd!")
            
        except Exception as e:
            logger.error(f"Fel vid bearbetning av filer: {str(e)}")

def main():
    parser = BitfinexDocsParser()
    parser.process_all_files()

if __name__ == '__main__':
    main()

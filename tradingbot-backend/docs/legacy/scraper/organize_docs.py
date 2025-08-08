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

class DocsOrganizer:
    def __init__(self, docs_dir: str = "cache/bitfinex_docs/docs"):
        """
        Initialiserar dokumentationsorganisatör
        
        Args:
            docs_dir: Sökväg till docs-katalogen
        """
        self.docs_dir = Path(docs_dir)
        self.output_dir = self.docs_dir.parent / "organized"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Skapa undermappar
        self.api_dir = self.output_dir / "api"
        self.symbols_dir = self.output_dir / "symbols"
        self.schemas_dir = self.output_dir / "schemas"
        
        for dir in [self.api_dir, self.symbols_dir, self.schemas_dir]:
            dir.mkdir(exist_ok=True)

    def merge_symbol_files(self) -> None:
        """Slår ihop alla symbol-filer till en strukturerad fil"""
        symbols = []
        
        # Läs alla symbol-filer
        for file in sorted(self.docs_dir.glob("all_symbols_*.json")):
            try:
                with file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'items' in data:
                        symbols.extend(data['items'])
                    else:
                        symbols.append(data)
            except Exception as e:
                logger.error(f"Fel vid läsning av {file}: {str(e)}")
                
        # Organisera symboler
        organized = {
            "crypto": [],
            "fiat": [],
            "stablecoin": [],
            "commodity": [],
            "test": [],
            "other": []
        }
        
        for symbol in symbols:
            if not isinstance(symbol, dict) or 'symbol' not in symbol:
                continue
                
            symbol_name = symbol['symbol']
            
            # Ta bort 't' prefix om det finns
            if symbol_name.startswith('t'):
                symbol_name = symbol_name[1:]
                
            # Kategorisera symbol
            if symbol_name.startswith('TEST'):
                category = 'test'
            else:
                # Hitta quote currency
                parts = symbol_name.split(':') if ':' in symbol_name else [symbol_name[:-3], symbol_name[-3:]]
                quote = parts[-1]
                
                if quote in ['BTC', 'ETH', 'LEO']:
                    category = 'crypto'
                elif quote in ['USD', 'EUR', 'GBP', 'JPY']:
                    category = 'fiat'
                elif quote in ['UST', 'USDT']:
                    category = 'stablecoin'
                elif quote == 'XAUT':
                    category = 'commodity'
                else:
                    category = 'other'
                    
            # Lägg till metadata
            metadata = {
                'symbol': symbol['symbol'],
                'base_currency': parts[0],
                'quote_currency': quote,
                'is_test': category == 'test',
                'is_paper': symbol.get('is_paper', False)
            }
            
            organized[category].append(metadata)
            
        # Spara kategoriserade symboler
        for category, symbols in organized.items():
            if not symbols:
                continue
                
            filename = f"{category}_symbols.json"
            filepath = self.symbols_dir / filename
            
            data = {
                "category": category,
                "description": self._get_category_description(category),
                "count": len(symbols),
                "symbols": sorted(symbols, key=lambda x: x['symbol'])
            }
            
            with filepath.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Sparade {len(symbols)} symboler i {filename}")

    def _get_category_description(self, category: str) -> str:
        """Returnerar beskrivning för en kategori"""
        descriptions = {
            'crypto': 'Handelspar med kryptovalutor som quote currency (BTC, ETH, LEO)',
            'fiat': 'Handelspar med fiatvalutor som quote currency (USD, EUR, GBP, etc.)',
            'stablecoin': 'Handelspar med stablecoins som quote currency (UST, USDT)',
            'commodity': 'Handelspar med råvaror som quote currency (XAUT)',
            'test': 'Testsymboler för utveckling och testning',
            'other': 'Övriga handelspar som inte passar i andra kategorier'
        }
        return descriptions.get(category, '')

    def extract_api_info(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extraherar API-information från HTML
        
        Args:
            html_content: HTML-innehåll att analysera
            
        Returns:
            Lista med API-information
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        api_info = []
        
        # Hitta alla API-sektioner
        for section in soup.find_all(['div', 'section'], class_=['api-section', 'endpoint', 'method']):
            endpoint = self._extract_endpoint(section)
            if endpoint:
                api_info.append(endpoint)
                
        return api_info

    def _extract_endpoint(self, section: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extraherar information om en endpoint"""
        try:
            # Hitta metod och sökväg
            method = None
            path = None
            
            # Sök i olika format
            method_elem = section.find(['span', 'div', 'code'], class_=['method', 'http-method'])
            if method_elem:
                method = method_elem.text.strip().upper()
            else:
                # Försök hitta i text
                text = section.get_text()
                methods = ['GET', 'POST', 'PUT', 'DELETE']
                for m in methods:
                    if m in text:
                        method = m
                        break
                        
            path_elem = section.find(['span', 'div', 'code'], class_=['path', 'endpoint', 'url'])
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
                'method': method,
                'path': path,
                'description': '',
                'authentication': False,
                'parameters': [],
                'response': {
                    'type': '',
                    'description': '',
                    'schema': {},
                    'examples': []
                }
            }
            
            # Hitta beskrivning
            desc_elem = section.find(['p', 'div'], class_=['description', 'docs'])
            if desc_elem:
                endpoint['description'] = desc_elem.text.strip()
                
            # Kontrollera autentisering
            auth_text = section.get_text().lower()
            endpoint['authentication'] = any(word in auth_text for word in ['authenticated', 'requires auth', 'authorization required'])
            
            # Hitta parametrar
            params = self._extract_parameters(section)
            if params:
                endpoint['parameters'] = params
                
            # Hitta svarsinformation
            response = self._extract_response(section)
            if response:
                endpoint['response'] = response
                
            return endpoint
            
        except Exception as e:
            logger.error(f"Fel vid extrahering av endpoint: {str(e)}")
            return None

    def _extract_parameters(self, section: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extraherar parametrar från en sektion"""
        parameters = []
        
        # Hitta parametertabell eller lista
        param_section = section.find(['table', 'div', 'ul'], class_=['parameters', 'params', 'arguments'])
        if not param_section:
            return parameters
            
        # Hitta alla parametrar
        for param in param_section.find_all(['tr', 'li', 'div'], class_=['parameter', 'argument']):
            try:
                param_info = {
                    'name': '',
                    'type': '',
                    'required': False,
                    'description': '',
                    'default': None
                }
                
                # Hitta namn
                name_elem = param.find(['td', 'span', 'code'], class_=['name', 'param-name'])
                if name_elem:
                    param_info['name'] = name_elem.text.strip()
                    
                # Hitta typ
                type_elem = param.find(['td', 'span', 'code'], class_=['type', 'param-type'])
                if type_elem:
                    param_info['type'] = type_elem.text.strip()
                    
                # Kontrollera om obligatorisk
                required_text = param.get_text().lower()
                param_info['required'] = 'required' in required_text and 'optional' not in required_text
                
                # Hitta beskrivning
                desc_elem = param.find(['td', 'span', 'p'], class_=['description', 'param-desc'])
                if desc_elem:
                    param_info['description'] = desc_elem.text.strip()
                    
                # Hitta standardvärde
                default_elem = param.find(['td', 'span', 'code'], class_=['default', 'param-default'])
                if default_elem:
                    param_info['default'] = default_elem.text.strip()
                    
                if param_info['name']:
                    parameters.append(param_info)
                    
            except Exception as e:
                logger.error(f"Fel vid extrahering av parameter: {str(e)}")
                continue
                
        return parameters

    def _extract_response(self, section: BeautifulSoup) -> Dict[str, Any]:
        """Extraherar svarsinformation från en sektion"""
        response = {
            'type': '',
            'description': '',
            'schema': {},
            'examples': []
        }
        
        # Hitta svarssektion
        response_section = section.find(['div', 'section'], class_=['response', 'returns', 'result'])
        if not response_section:
            return response
            
        try:
            # Hitta typ
            type_elem = response_section.find(['span', 'code'], class_=['type', 'response-type'])
            if type_elem:
                response['type'] = type_elem.text.strip()
                
            # Hitta beskrivning
            desc_elem = response_section.find(['p', 'div'], class_=['description', 'response-desc'])
            if desc_elem:
                response['description'] = desc_elem.text.strip()
                
            # Hitta schema
            schema_elem = response_section.find(['pre', 'code'], class_=['schema', 'json-schema'])
            if schema_elem:
                try:
                    schema_text = schema_elem.text.strip()
                    if schema_text:
                        response['schema'] = json.loads(schema_text)
                except json.JSONDecodeError:
                    pass
                    
            # Hitta exempel
            for example in response_section.find_all(['pre', 'code'], class_=['example', 'json-example']):
                try:
                    example_text = example.text.strip()
                    if example_text:
                        response['examples'].append(json.loads(example_text))
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.error(f"Fel vid extrahering av svar: {str(e)}")
            
        return response

    def process_api_file(self, file_path: Path) -> None:
        """
        Bearbetar en API-dokumentationsfil
        
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
                # Extrahera API-information från HTML
                endpoints = self.extract_api_info(data['html'])
            else:
                # Använd data direkt
                endpoints = [data]
                
            if not endpoints:
                logger.warning(f"Inga endpoints hittades i {file_path}")
                return
                
            # Kategorisera och spara endpoints
            for endpoint in endpoints:
                self._save_endpoint(endpoint, file_path.stem)
                
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {file_path}: {str(e)}")

    def _save_endpoint(self, endpoint: Dict[str, Any], source: str) -> None:
        """
        Sparar en endpoint i rätt kategori
        
        Args:
            endpoint: Endpoint att spara
            source: Källfil
        """
        # Bestäm kategori
        if 'websocket' in source.lower() or 'ws' in source.lower():
            base_dir = self.api_dir / 'websocket'
        else:
            base_dir = self.api_dir / 'rest'
            
        # Skapa underkatalog baserat på autentisering
        if endpoint.get('authentication', False):
            subdir = base_dir / 'authenticated'
        else:
            subdir = base_dir / 'public'
            
        subdir.mkdir(parents=True, exist_ok=True)
        
        # Skapa filnamn från sökväg
        path = endpoint.get('path', '').strip('/')
        if not path:
            path = 'unknown'
        filename = f"{path.replace('/', '_')}.json"
        
        # Lägg till källinformation
        endpoint['source'] = source
        
        # Spara endpoint
        filepath = subdir / filename
        with filepath.open('w', encoding='utf-8') as f:
            json.dump(endpoint, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Sparade endpoint från {source} till {filepath}")

    def create_index(self) -> None:
        """Skapar en index-fil för all dokumentation"""
        index = {
            "title": "Bitfinex API Documentation",
            "description": "Strukturerad dokumentation för Bitfinex API",
            "api": {
                "rest": self._index_api_category("rest"),
                "websocket": self._index_api_category("websocket")
            },
            "symbols": self._index_symbols(),
            "schemas": self._index_schemas()
        }
        
        # Spara index
        with (self.output_dir / "index.json").open('w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
        logger.info("Skapade index.json")

    def _index_api_category(self, category: str) -> Dict[str, Any]:
        """Indexerar en API-kategori"""
        result = {
            "authenticated": {"endpoints": []},
            "public": {"endpoints": []}
        }
        
        base_dir = self.api_dir / category
        if not base_dir.exists():
            return result
            
        for auth_type in ['authenticated', 'public']:
            subdir = base_dir / auth_type
            if not subdir.exists():
                continue
                
            endpoints = []
            for file in subdir.glob("*.json"):
                try:
                    with file.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    endpoints.append({
                        "method": data.get("method", ""),
                        "path": data.get("path", ""),
                        "description": data.get("description", ""),
                        "source": data.get("source", ""),
                        "file": file.name
                    })
                except Exception as e:
                    logger.error(f"Fel vid indexering av {file}: {str(e)}")
                    
            result[auth_type]["endpoints"] = sorted(endpoints, key=lambda x: x["path"])
            result[auth_type]["count"] = len(endpoints)
            
        return result

    def _index_symbols(self) -> Dict[str, Any]:
        """Indexerar symboler"""
        result = {}
        
        for file in self.symbols_dir.glob("*_symbols.json"):
            try:
                with file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                category = data["category"]
                result[category] = {
                    "description": data["description"],
                    "count": data["count"],
                    "file": file.name
                }
            except Exception as e:
                logger.error(f"Fel vid indexering av {file}: {str(e)}")
                
        return result

    def _index_schemas(self) -> Dict[str, Any]:
        """Indexerar scheman"""
        result = {}
        
        for file in self.schemas_dir.glob("*.json"):
            try:
                with file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                result[file.stem] = {
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "file": file.name
                }
            except Exception as e:
                logger.error(f"Fel vid indexering av {file}: {str(e)}")
                
        return result

    def organize_all(self) -> None:
        """Organiserar all dokumentation"""
        try:
            # Rensa output-katalog
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True)
            
            # Återskapa struktur
            for dir in [self.api_dir, self.symbols_dir, self.schemas_dir]:
                dir.mkdir(exist_ok=True)
            
            # Slå ihop symboler
            self.merge_symbol_files()
            
            # Bearbeta API-filer
            api_files = [
                'rest_auth.json',
                'rest-public.json',
                'ws_auth.json',
                'ws-public.json',
                'margin_account.json',
                'order_types.json',
                'positions_account.json',
                'wallet_account.json'
            ]
            
            for filename in api_files:
                file_path = self.docs_dir / filename
                if file_path.exists():
                    self.process_api_file(file_path)
                    
            # Skapa index
            self.create_index()
            
            logger.info("Dokumentationsorganisering slutförd!")
            
        except Exception as e:
            logger.error(f"Fel vid organisering av dokumentation: {str(e)}")

def main():
    organizer = DocsOrganizer()
    organizer.organize_all()

if __name__ == '__main__':
    main()

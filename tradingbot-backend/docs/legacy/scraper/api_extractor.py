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

class ApiExtractor:
    def __init__(self, input_dir: str = "cache/bitfinex_docs/json/other"):
        """
        Initialiserar API-extraktor
        
        Args:
            input_dir: Sökväg till input-katalogen
        """
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir.parent.parent / "api"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Skapa undermappar
        self.rest_dir = self.output_dir / "rest"
        self.ws_dir = self.output_dir / "websocket"
        
        for dir in [self.rest_dir, self.ws_dir]:
            dir.mkdir(exist_ok=True)

    def find_api_info(self, data: Any) -> List[Dict[str, Any]]:
        """
        Hittar API-information i data
        
        Args:
            data: Data att söka i
            
        Returns:
            Lista med API-information
        """
        api_info = []
        
        if isinstance(data, dict):
            # Kontrollera om detta är en endpoint
            if "api_method" in data:
                api_info.append(self._extract_endpoint(data))
            else:
                # Sök rekursivt i alla värden
                for value in data.values():
                    api_info.extend(self.find_api_info(value))
        elif isinstance(data, list):
            # Sök i varje element
            for item in data:
                api_info.extend(self.find_api_info(item))
                
        return api_info

    def _extract_endpoint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extraherar information från en endpoint
        
        Args:
            data: Endpoint-data
            
        Returns:
            Endpoint-information
        """
        # Hitta beskrivning
        description = data.get("api_description", data.get("description", ""))
        
        # Hitta sökväg
        path = data.get("api_path", data.get("path", ""))
        if not path and "api_url" in data:
            # Extrahera sökväg från URL
            url = data["api_url"]
            if isinstance(url, str):
                path = re.sub(r'^https?://[^/]+', '', url)
                
        endpoint = {
            "method": data.get("api_method", data.get("method", "")).upper(),
            "path": path,
            "description": description,
            "authentication": data.get("api_auth", data.get("authentication", False)),
            "parameters": self._extract_parameters(data),
            "response": self._extract_response(data),
            "examples": self._extract_examples(data)
        }
        
        # Kontrollera om det finns autentiseringskrav i parametrarna
        if any(p.get("name") in ["api_key", "api_secret"] for p in endpoint["parameters"]):
            endpoint["authentication"] = True
            
        return endpoint

    def _extract_parameters(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extraherar parametrar"""
        parameters = []
        
        # Hitta parametrar på olika platser
        param_sources = [
            ("api_parameters", data.get("api_parameters", [])),
            ("api_args", data.get("api_args", [])),
            ("api_body", data.get("api_body", {})),
            ("parameters", data.get("parameters", [])),
            ("params", data.get("params", [])),
            ("args", data.get("args", []))
        ]
        
        for source_name, params in param_sources:
            if isinstance(params, dict):
                # Hantera nästlade parametrar
                for key, value in params.items():
                    if isinstance(value, dict):
                        param_info = {
                            "name": key,
                            "type": value.get("type", ""),
                            "required": value.get("required", False),
                            "description": value.get("description", ""),
                            "default": value.get("default"),
                            "example": value.get("example")
                        }
                        
                        # Lägg till schema-information
                        schema = value.get("schema", {})
                        if schema:
                            param_info.update({
                                "type": schema.get("type", param_info["type"]),
                                "format": schema.get("format", ""),
                                "enum": schema.get("enum", [])
                            })
                            
                        if param_info["name"]:
                            parameters.append(param_info)
            elif isinstance(params, list):
                for param in params:
                    try:
                        if isinstance(param, dict):
                            param_info = {
                                "name": param.get("name", ""),
                                "type": param.get("type", param.get("in", "")),
                                "required": param.get("required", False),
                                "description": param.get("description", ""),
                                "default": param.get("default"),
                                "example": param.get("example")
                            }
                            
                            # Lägg till schema-information
                            schema = param.get("schema", {})
                            if schema:
                                param_info.update({
                                    "type": schema.get("type", param_info["type"]),
                                    "format": schema.get("format", ""),
                                    "enum": schema.get("enum", [])
                                })
                                
                            if param_info["name"]:
                                parameters.append(param_info)
                                
                    except Exception as e:
                        logger.error(f"Fel vid extrahering av parameter: {str(e)}")
                        continue
                        
        return parameters

    def _extract_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extraherar svarsinformation"""
        response = {
            "type": "",
            "description": "",
            "schema": {},
            "examples": []
        }
        
        # Hitta svarsinformation på olika platser
        response_sources = [
            ("api_response", data.get("api_response", {})),
            ("api_result", data.get("api_result", {})),
            ("responses", data.get("responses", {}))
        ]
        
        for source_name, responses in response_sources:
            if isinstance(responses, dict):
                # Hitta framgångsrikt svar
                success_response = None
                
                # Först leta efter 200-svar
                for code in ["200", "201", "202", "203", "204", "205", "206"]:
                    if code in responses:
                        success_response = responses[code]
                        break
                        
                # Om inget 200-svar hittades, använd hela objektet
                if not success_response:
                    success_response = responses
                    
                if success_response:
                    response.update({
                        "type": success_response.get("type", success_response.get("content_type", "")),
                        "description": success_response.get("description", ""),
                        "schema": success_response.get("schema", success_response.get("content", {}))
                    })
                    
                    # Hitta exempel
                    examples = success_response.get("examples", [])
                    if isinstance(examples, list):
                        response["examples"].extend(examples)
                    elif isinstance(examples, dict):
                        for example in examples.values():
                            if isinstance(example, dict) and "value" in example:
                                try:
                                    if isinstance(example["value"], str):
                                        example_value = json.loads(example["value"])
                                    else:
                                        example_value = example["value"]
                                    response["examples"].append(example_value)
                                except json.JSONDecodeError:
                                    response["examples"].append(example["value"])
                                    
        return response

    def _extract_examples(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extraherar exempel"""
        examples = []
        
        # Hitta exempel på olika platser
        example_sources = [
            ("api_examples", data.get("api_examples", [])),
            ("api_sample", data.get("api_sample", [])),
            ("examples", data.get("examples", [])),
            ("sample", data.get("sample", [])),
            ("code", data.get("code", []))
        ]
        
        for source_name, raw_examples in example_sources:
            if isinstance(raw_examples, list):
                for example in raw_examples:
                    try:
                        if isinstance(example, str):
                            # Försök parsa som JSON
                            try:
                                example = json.loads(example)
                            except json.JSONDecodeError:
                                pass
                                
                        if isinstance(example, dict):
                            example_info = {
                                "title": example.get("title", ""),
                                "description": example.get("description", ""),
                                "request": example.get("request", {}),
                                "response": example.get("response", {})
                            }
                        else:
                            example_info = {
                                "content": example
                            }
                            
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
        if 'websocket' in source.lower() or 'ws' in source.lower():
            category = 'websocket'
        else:
            category = 'rest'
            
        # Bestäm underkategori baserat på sökväg och autentisering
        path = endpoint.get('path', '').lower()
        
        if endpoint.get('authentication', False) or any(word in path for word in ['auth', 'key', 'private']):
            subcategory = 'authenticated'
        else:
            subcategory = 'public'
            
        return category, subcategory

    def save_endpoint(self, endpoint: Dict[str, Any], category: str, subcategory: str, source: str) -> None:
        """
        Sparar en endpoint
        
        Args:
            endpoint: Endpoint att spara
            category: Huvudkategori
            subcategory: Underkategori
            source: Källfil
        """
        # Välj rätt katalog
        if category == 'websocket':
            base_dir = self.ws_dir
        else:
            base_dir = self.rest_dir
            
        # Skapa underkatalog
        subdir = base_dir / subcategory
        subdir.mkdir(exist_ok=True)
        
        # Skapa filnamn från sökväg
        path = endpoint['path'].strip('/')
        if not path:
            path = 'unknown'
        filename = f"{path.replace('/', '_')}.json"
        
        # Lägg till källinformation
        endpoint['source'] = source
        
        # Spara endpoint
        filepath = subdir / filename
        with filepath.open('w', encoding='utf-8') as f:
            json.dump(endpoint, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Sparade {category}/{subcategory}/{filename}")

    def create_index(self) -> None:
        """Skapar en index-fil"""
        index = {
            "title": "Bitfinex API Documentation",
            "description": "Strukturerad API-dokumentation för Bitfinex",
            "categories": {
                "rest": self._index_category("rest"),
                "websocket": self._index_category("websocket")
            }
        }
        
        # Spara index
        with (self.output_dir / "index.json").open('w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
        logger.info("Skapade index.json")

    def _index_category(self, category: str) -> Dict[str, Any]:
        """Indexerar en kategori"""
        result = {
            "authenticated": {"endpoints": []},
            "public": {"endpoints": []}
        }
        
        base_dir = self.rest_dir if category == "rest" else self.ws_dir
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
                
            # Hitta API-information
            endpoints = self.find_api_info(data)
            
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
    extractor = ApiExtractor()
    extractor.process_all_files()

if __name__ == '__main__':
    main()
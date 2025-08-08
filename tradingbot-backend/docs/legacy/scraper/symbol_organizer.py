import json
from pathlib import Path
from typing import Dict, List, Any
import logging

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SymbolOrganizer:
    def __init__(self, input_dir: str = "cache/bitfinex_docs/extracted"):
        """
        Initialiserar symbol-organisatören
        
        Args:
            input_dir: Sökväg till katalogen med extraherade filer
        """
        self.input_dir = Path(input_dir)
        self.symbols_dir = self.input_dir / "symbols"
        self.symbols_dir.mkdir(exist_ok=True)

    def categorize_symbol(self, symbol: str) -> str:
        """
        Kategoriserar en handelssymbol
        
        Args:
            symbol: Symbol att kategorisera
            
        Returns:
            Kategori för symbolen
        """
        # Ta bort 't' prefix om det finns
        if symbol.startswith('t'):
            symbol = symbol[1:]
            
        # Kontrollera om det är en testsymbol
        if symbol.startswith('TEST'):
            return 'test'
            
        # Hitta quote currency
        parts = symbol.split(':') if ':' in symbol else [symbol]
        quote = parts[-1]
        
        # Kategorisera baserat på quote currency
        if quote in ['BTC', 'ETH', 'LEO']:
            return 'crypto'
        elif quote in ['USD', 'USDQ', 'USDR']:
            return 'usd'
        elif quote in ['UST', 'USDT']:
            return 'stablecoin'
        elif quote in ['EUR', 'EURQ', 'EURR', 'GBP', 'JPY', 'TRY']:
            return 'fiat'
        elif quote == 'XAUT':
            return 'commodity'
        else:
            return 'other'

    def organize_symbols(self, symbols: List[Dict[str, str]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Organiserar symboler i kategorier
        
        Args:
            symbols: Lista med symboler att organisera
            
        Returns:
            Dictionary med kategoriserade symboler
        """
        categories = {
            'crypto': [],
            'usd': [],
            'stablecoin': [],
            'fiat': [],
            'commodity': [],
            'test': [],
            'other': []
        }
        
        for symbol_data in symbols:
            symbol = symbol_data['symbol']
            category = self.categorize_symbol(symbol)
            
            # Lägg till metadata
            metadata = {
                'symbol': symbol,
                'base_currency': self.get_base_currency(symbol),
                'quote_currency': self.get_quote_currency(symbol),
                'is_test': category == 'test',
                'is_paper': symbol_data.get('is_paper', False)
            }
            
            categories[category].append(metadata)
            
        return categories

    def get_base_currency(self, symbol: str) -> str:
        """Extraherar base currency från en symbol"""
        # Ta bort 't' prefix om det finns
        if symbol.startswith('t'):
            symbol = symbol[1:]
            
        # Ta bort TEST prefix om det finns
        if symbol.startswith('TEST'):
            symbol = symbol[4:]
            
        # Dela upp i base och quote
        parts = symbol.split(':') if ':' in symbol else [symbol[:-3], symbol[-3:]]
        return parts[0]

    def get_quote_currency(self, symbol: str) -> str:
        """Extraherar quote currency från en symbol"""
        # Ta bort 't' prefix om det finns
        if symbol.startswith('t'):
            symbol = symbol[1:]
            
        # Ta bort TEST prefix om det finns
        if symbol.startswith('TEST'):
            symbol = symbol[4:]
            
        # Dela upp i base och quote
        parts = symbol.split(':') if ':' in symbol else [symbol[:-3], symbol[-3:]]
        return parts[-1]

    def save_categories(self, categories: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Sparar kategoriserade symboler
        
        Args:
            categories: Dictionary med kategoriserade symboler
        """
        # Spara varje kategori separat
        for category, symbols in categories.items():
            if not symbols:
                continue
                
            filename = f"{category}_symbols.json"
            filepath = self.symbols_dir / filename
            
            data = {
                "category": category,
                "description": self.get_category_description(category),
                "count": len(symbols),
                "symbols": sorted(symbols, key=lambda x: x['symbol'])
            }
            
            with filepath.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Sparade {len(symbols)} symboler i {filename}")
            
        # Skapa en översiktsfil
        self.create_summary()

    def get_category_description(self, category: str) -> str:
        """Returnerar beskrivning för en kategori"""
        descriptions = {
            'crypto': 'Handelspar med kryptovalutor som quote currency (BTC, ETH, LEO)',
            'usd': 'Handelspar med USD och USD-varianter som quote currency',
            'stablecoin': 'Handelspar med stablecoins som quote currency (UST, USDT)',
            'fiat': 'Handelspar med fiatvalutor som quote currency (EUR, GBP, JPY, etc.)',
            'commodity': 'Handelspar med råvaror som quote currency (XAUT)',
            'test': 'Testsymboler för utveckling och testning',
            'other': 'Övriga handelspar som inte passar i andra kategorier'
        }
        return descriptions.get(category, '')

    def create_summary(self) -> None:
        """Skapar en översiktsfil för alla symbolkategorier"""
        summary = {
            "title": "Bitfinex Trading Symbols Overview",
            "description": "Översikt över alla tillgängliga handelssymboler på Bitfinex",
            "categories": []
        }
        
        # Samla information från alla kategorifiler
        for filepath in sorted(self.symbols_dir.glob("*_symbols.json")):
            with filepath.open('r', encoding='utf-8') as f:
                data = json.load(f)
                
            summary["categories"].append({
                "name": data["category"],
                "description": data["description"],
                "count": data["count"],
                "file": filepath.name
            })
            
        # Spara översikt
        with (self.symbols_dir / "overview.json").open('w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        logger.info("Skapade symbols/overview.json")

def main():
    # Läs symbols från all_symbols.json
    input_file = Path("cache/bitfinex_docs/extracted/docs/all_symbols.json")
    with input_file.open('r', encoding='utf-8') as f:
        data = json.load(f)
        symbols = data['items']
    
    # Organisera och spara symboler
    organizer = SymbolOrganizer()
    categories = organizer.organize_symbols(symbols)
    organizer.save_categories(categories)

if __name__ == '__main__':
    main()

# Web Scraping - TradingBot Backend

Detta dokument beskriver hur web scraping används i tradingboten för att hämta och strukturera information från Bitfinex API-dokumentation.

## Innehåll

1. [Översikt](#översikt)
2. [Scraper-moduler](#scraper-moduler)
3. [Användningsområden](#användningsområden)
4. [Cachehantering](#cachehantering)
5. [Exempel](#exempel)
6. [Säkerhet och etik](#säkerhet-och-etik)

## Översikt

Web scraping-funktionaliteten i tradingboten används för att automatiskt hämta och strukturera information från Bitfinex API-dokumentation. Detta hjälper till att hålla projektet uppdaterat med senaste API-ändringar, validera orderparametrar, och generera korrekt formaterade API-anrop.

Scrapern är uppdelad i flera moduler som fokuserar på olika aspekter av API-dokumentationen:
- **Allmän API-information** (endpoints, felkoder, symboler)
- **Autentiseringsinformation** (REST och WebSocket)
- **Konto-relaterad information** (wallet, positions, margin)

## Scraper-moduler

### BitfinexDocsScraper (`scraper/bitfinex_docs.py`)

Denna modul hämtar och extraherar allmän information från Bitfinex API-dokumentation:

- **Endpoints**: Lista över tillgängliga API-endpoints med beskrivningar och parametrar
- **Felkoder**: Information om API-felkoder och deras betydelse
- **Symboler**: Lista över tillgängliga handelspar
- **Ordertyper**: Information om olika ordertyper och deras parametrar

```python
from scraper.bitfinex_docs import BitfinexDocsScraper

# Skapa en instans av scrapern
scraper = BitfinexDocsScraper()

# Hämta all dokumentation
scraper.fetch_all_documentation()
scraper.fetch_error_codes()
scraper.fetch_symbols()
scraper.fetch_order_types()

# Hämta information om en specifik ordertyp
order_type_info = scraper.get_order_type_info("EXCHANGE LIMIT")
print(f"Krävda parametrar för EXCHANGE LIMIT: {order_type_info['required_params']}")
```

### BitfinexAuthScraper (`scraper/bitfinex_auth_docs.py`)

Denna modul fokuserar på autentiseringsinformation för Bitfinex API:

- **REST autentisering**: Headers, nonce-hantering, signaturgeneration
- **WebSocket autentisering**: Payload-format, nonce-hantering, signaturgeneration
- **Tillgängliga autentiserade endpoints**: Lista över endpoints som kräver autentisering
- **Tillgängliga WebSocket events**: Lista över autentiserade WebSocket-events

```python
from scraper.bitfinex_auth_docs import BitfinexAuthScraper

# Skapa en instans av auth-scrapern
auth_scraper = BitfinexAuthScraper()

# Hämta autentiseringsinformation
rest_info = auth_scraper.fetch_rest_auth_info()
ws_info = auth_scraper.fetch_ws_auth_info()

# Generera rekommendationer för autentisering
recommendations = auth_scraper.get_auth_recommendations()
print(f"REST autentiseringsrekommendationer: {recommendations['rest']}")

# Generera kodexempel
examples = auth_scraper.generate_auth_code_examples()
print(f"REST autentiseringskodexempel:\n{examples['rest']['python']['build_auth_headers']}")
```

### BitfinexAccountScraper (`scraper/bitfinex_account_docs.py`)

Denna modul fokuserar på konto-relaterad information:

- **Wallet**: Information om wallet-endpoints och svarsfält
- **Positions**: Information om positions-endpoints och svarsfält
- **Margin**: Information om margin-endpoints och svarsfält

```python
from scraper.bitfinex_account_docs import BitfinexAccountScraper

# Skapa en instans av account-scrapern
account_scraper = BitfinexAccountScraper()

# Hämta konto-relaterad information
wallet_info = account_scraper.fetch_wallet_info()
positions_info = account_scraper.fetch_positions_info()
margin_info = account_scraper.fetch_margin_info()

# Generera kodexempel
examples = account_scraper.generate_account_code_examples()
print(f"Wallet kodexempel:\n{examples['wallet']['python']}")
```

## Användningsområden

Web scraping-funktionaliteten används i flera delar av tradingboten:

### 1. Ordervalidering

`rest/order_validator.py` använder information från `BitfinexDocsScraper` för att validera orderparametrar innan de skickas till API:et:

```python
from scraper.bitfinex_docs import BitfinexDocsScraper

class OrderValidator:
    def __init__(self):
        self.scraper = BitfinexDocsScraper()
        self.scraper.fetch_order_types()
        
    def validate_order(self, order_data):
        order_type = order_data.get("type", "").upper()
        order_type_info = self.scraper.get_order_type_info(order_type)
        
        if not order_type_info:
            return False, f"Ogiltig ordertyp: {order_type}"
        
        # Kontrollera krävda parametrar
        for param in order_type_info["required_params"]:
            if param not in order_data or not order_data[param]:
                return False, f"Saknad parameter: {param}"
                
        return True, "Order validerad"
```

### 2. Autentiseringshantering

`rest/auth.py` och `ws/auth.py` använder information från `BitfinexAuthScraper` för att säkerställa korrekt autentisering:

```python
from scraper.bitfinex_auth_docs import BitfinexAuthScraper

def update_auth_implementation():
    auth_scraper = BitfinexAuthScraper()
    recommendations = auth_scraper.get_auth_recommendations()
    
    # Uppdatera nonce-generering baserat på rekommendationer
    nonce_generation = recommendations["rest"]["nonce_generation"]
    if "mikrosekunder" in nonce_generation:
        nonce_multiplier = 1_000_000
    else:
        nonce_multiplier = 1_000
```

### 3. Kodgenerering

Scrapern används för att generera kodexempel och hjälpa utvecklare att förstå API:et:

```python
from scraper.bitfinex_account_docs import BitfinexAccountScraper

def generate_account_code():
    account_scraper = BitfinexAccountScraper()
    examples = account_scraper.generate_account_code_examples()
    
    # Spara kodexempel till filer
    with open("examples/wallet_example.py", "w") as f:
        f.write(examples["wallet"]["python"])
```

## Cachehantering

För att undvika att överbelasta Bitfinex API-dokumentationsserver och för att förbättra prestanda, implementerar scrapern en cachehantering:

- Cachad data sparas i `cache/bitfinex_docs/` katalogen
- Cachen är giltig i 7 dagar (konfigurerbart)
- Om nätverksanslutningen misslyckas, används cachad data även om den är äldre än giltighetsperioden

```python
def _get_cached_or_fetch(self, url: str, section: str) -> dict:
    cache_file = self.cache_dir / f"{section}.json"
    
    # Kontrollera om cachen finns och är giltig
    if cache_file.exists():
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age < timedelta(days=self.cache_validity_days):
            # Använd cachad data
            return json.load(open(cache_file))
    
    # Hämta från webben och spara till cache
    response = self.session.get(url)
    data = response.json() if "application/json" in response.headers.get("Content-Type", "") else {"html": response.text}
    json.dump(data, open(cache_file, "w"))
    
    return data
```

## Exempel

### Exempel 1: Hämta information om ordertyper

```python
from scraper.bitfinex_docs import BitfinexDocsScraper

def print_order_types_info():
    scraper = BitfinexDocsScraper()
    scraper.fetch_order_types()
    
    print("Tillgängliga ordertyper:")
    for order_type, info in scraper.order_types.items():
        print(f"\n{order_type}:")
        print(f"  Beskrivning: {info['description']}")
        print(f"  Krävda parametrar: {', '.join(info['required_params'])}")
        print(f"  Valfria parametrar: {', '.join(info['optional_params'])}")

if __name__ == "__main__":
    print_order_types_info()
```

### Exempel 2: Validera autentiseringsimplementation

```python
from scraper.bitfinex_auth_docs import BitfinexAuthScraper

def validate_auth_implementation():
    # Läs nuvarande implementation
    with open("rest/auth.py", "r") as f:
        rest_auth_code = f.read()
    
    with open("ws/auth.py", "r") as f:
        ws_auth_code = f.read()
    
    # Skapa scrapern och jämför
    auth_scraper = BitfinexAuthScraper()
    auth_scraper.fetch_rest_auth_info()
    auth_scraper.fetch_ws_auth_info()
    
    comparison = auth_scraper.compare_with_current_implementation(
        rest_auth_code=rest_auth_code,
        ws_auth_code=ws_auth_code
    )
    
    # Visa resultat
    print("REST Auth validering:")
    if comparison["rest"]["matches_recommendations"]:
        print("✅ Implementationen följer rekommendationerna")
    else:
        print("⚠️ Implementationen avviker från rekommendationerna:")
        for diff in comparison["rest"]["differences"]:
            print(f"  - {diff['recommendation']}")
    
    print("\nWebSocket Auth validering:")
    if comparison["websocket"]["matches_recommendations"]:
        print("✅ Implementationen följer rekommendationerna")
    else:
        print("⚠️ Implementationen avviker från rekommendationerna:")
        for diff in comparison["websocket"]["differences"]:
            print(f"  - {diff['recommendation']}")

if __name__ == "__main__":
    validate_auth_implementation()
```

### Exempel 3: Generera dokumentation för API-endpoints

```python
from scraper.bitfinex_auth_docs import BitfinexAuthScraper

def generate_api_docs():
    auth_scraper = BitfinexAuthScraper()
    rest_info = auth_scraper.fetch_rest_auth_info()
    
    # Skapa markdown-dokumentation
    with open("docs/api_endpoints.md", "w") as f:
        f.write("# Bitfinex API Endpoints\n\n")
        
        for section in rest_info["endpoint_sections"]:
            f.write(f"## {section['category']}\n\n")
            
            for endpoint in section["endpoints"]:
                f.write(f"### {endpoint['name']}\n\n")
                if endpoint.get("url"):
                    f.write(f"Dokumentation: [{endpoint['name']}]({endpoint['url']})\n\n")

if __name__ == "__main__":
    generate_api_docs()
```

## Säkerhet och etik

Vid användning av web scraping är det viktigt att tänka på följande:

1. **Respektera robots.txt**: Scrapern är konfigurerad att respektera `robots.txt` för att inte överbelasta servern.

2. **Cachehantering**: Implementationen använder caching för att minimera antalet förfrågningar till dokumentationsservern.

3. **User-Agent**: Scrapern använder en tydlig User-Agent som identifierar sig som ett verktyg för Genesis-Trading-Bot.

4. **Rate-limiting**: Scrapern lägger in pauser mellan förfrågningar för att inte överbelasta servern.

5. **Endast offentlig dokumentation**: Scrapern hämtar endast offentligt tillgänglig dokumentation, inte privat information eller data som kräver inloggning.

```python
# Exempel på hur User-Agent är konfigurerad
self.session.headers.update({
    "User-Agent": "Mozilla/5.0 Genesis-Trading-Bot Documentation Helper"
})

# Exempel på rate-limiting
time.sleep(0.5)  # Vänta 500ms mellan förfrågningar
```

Genom att följa dessa riktlinjer säkerställer vi att web scraping-funktionaliteten används på ett ansvarsfullt och etiskt sätt.

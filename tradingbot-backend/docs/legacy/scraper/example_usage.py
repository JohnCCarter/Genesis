"""
Exempel på hur man använder BitfinexDocsScraper.

Detta skript visar hur man kan använda BitfinexDocsScraper för att hämta
och visa information om Bitfinex API.
"""

import json
import os
import sys
from pathlib import Path

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.bitfinex_docs import BitfinexDocsScraper


def print_section_header(title):
    """Skriv ut en formaterad sektionsrubrik."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def show_symbols(scraper):
    """Visa symboler från Bitfinex API."""
    print_section_header("SYMBOLER")

    symbols = scraper.fetch_symbols()
    print(f"Hittade totalt {len(symbols)} symboler")

    # Visa några vanliga symboler
    common_symbols = [
        s for s in symbols if s["symbol"] in ["tBTCUSD", "tETHUSD", "tLTCUSD"]
    ]
    print("\nVanliga symboler:")
    for symbol in common_symbols:
        print(f"  {symbol['symbol']}")

    # Visa paper trading symboler
    paper_symbols = scraper.get_paper_trading_symbols()
    print("\nPaper trading symboler:")
    for symbol in paper_symbols:
        print(f"  {symbol['symbol']}")

    # Spara alla symboler till en JSON-fil
    output_file = Path("cache/bitfinex_docs/all_symbols.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(symbols, f, indent=2)
    print(f"\nAlla symboler sparade till {output_file}")


def show_order_types(scraper):
    """Visa ordertyper från Bitfinex API."""
    print_section_header("ORDERTYPER")

    order_types = scraper.fetch_order_types()
    print(f"Hittade totalt {len(order_types)} ordertyper")

    print("\nDetaljer om ordertyper:")
    for name, info in order_types.items():
        print(f"\n  {name}:")
        print(f"    Beskrivning: {info['description']}")
        print(f"    Krävda parametrar: {', '.join(info['required_params'])}")
        print(f"    Valfria parametrar: {', '.join(info['optional_params'])}")


def show_error_codes(scraper):
    """Visa felkoder från Bitfinex API."""
    print_section_header("FELKODER")

    error_codes = scraper.fetch_error_codes()
    print(f"Hittade totalt {len(error_codes)} felkoder")

    if error_codes:
        print("\nExempel på felkoder:")
        for i, (code, info) in enumerate(list(error_codes.items())[:5]):
            print(f"\n  {code}:")
            print(f"    Meddelande: {info.get('message', 'N/A')}")
            print(f"    Beskrivning: {info.get('description', 'N/A')}")
            if i >= 4:  # Visa max 5 exempel
                break
    else:
        print(
            "\nKunde inte hämta felkoder. Detta kan bero på ändringar i API-dokumentationen."
        )
        print("Vanliga felkoder inkluderar:")
        print("  - 10100: Pris utanför tillåtet intervall")
        print("  - 10001: Otillräckliga medel")
        print("  - 10020: Ogiltig nonce (för liten)")
        print("  - 20060: Ogiltig API-nyckel")


def show_documentation_summary(scraper):
    """Visa en sammanfattning av dokumentationen."""
    print_section_header("DOKUMENTATIONSSAMMANFATTNING")

    summary = scraper.generate_documentation_summary()
    print(f"Endpoints: {summary['endpoints_count']}")
    print(f"Felkoder: {summary['error_codes_count']}")
    print(f"Symboler: {summary['symbols_count']}")
    print(f"Ordertyper: {summary['order_types_count']}")
    print(f"Senast uppdaterad: {summary['last_updated']}")


def show_cache_files(scraper):
    """Visa cachade filer."""
    print_section_header("CACHE-FILER")

    cache_dir = scraper.cache_dir
    print(f"Cache-katalog: {cache_dir}")

    if os.path.exists(cache_dir):
        files = os.listdir(cache_dir)
        print(f"Antal filer: {len(files)}")
        print("\nFiler:")
        for file in files:
            file_path = os.path.join(cache_dir, file)
            size = os.path.getsize(file_path) / 1024  # KB
            print(f"  {file} ({size:.1f} KB)")
    else:
        print("Cache-katalogen existerar inte ännu.")


def main():
    """Huvudfunktion för att visa exempel på användning av BitfinexDocsScraper."""
    print_section_header("BITFINEX DOCS SCRAPER - EXEMPEL")
    print("Detta skript visar hur man kan använda BitfinexDocsScraper för att hämta")
    print("och visa information om Bitfinex API.")

    # Skapa en instans av scrapern
    scraper = BitfinexDocsScraper()

    # Visa olika typer av information
    show_symbols(scraper)
    show_order_types(scraper)
    show_error_codes(scraper)
    show_documentation_summary(scraper)
    show_cache_files(scraper)

    print("\nExempel slutfört!")


if __name__ == "__main__":
    main()

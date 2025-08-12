"""
Authentication Examples - TradingBot Backend

Detta skript visar exempel på hur man kan använda autentiseringsinformation
från BitfinexAuthScraper för både REST och WebSocket API.
"""

import os
import sys

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.bitfinex_auth_docs import BitfinexAuthScraper

from utils.logger import get_logger

logger = get_logger("auth_examples")


def display_rest_auth_info():
    """
    Visar information om REST API autentisering.
    """
    print("\n=== REST API Authentication Information ===\n")

    # Skapa en instans av BitfinexAuthScraper
    scraper = BitfinexAuthScraper()

    # Hämta REST autentiseringsinformation
    rest_info = scraper.fetch_rest_auth_info()

    # Visa autentiseringsprocess
    print("📝 REST Autentiseringsprocess:")
    if "auth_process" in rest_info:
        for i, step in enumerate(rest_info["auth_process"], 1):
            print(f"  {i}. {step}")
    else:
        print("  Ingen autentiseringsprocess hittad i dokumentationen.")

    # Visa autentiseringsheaders
    print("\n🔑 REST Autentiseringsheaders:")
    if "auth_headers" in rest_info and rest_info["auth_headers"]:
        for header in rest_info["auth_headers"]:
            print(f"  - {header}")
    else:
        print("  Inga autentiseringsheaders hittade i dokumentationen.")

    # Visa nonce-information
    print("\n⏱️ REST Nonce-information:")
    if "nonce_info" in rest_info and rest_info["nonce_info"]:
        nonce_info = rest_info["nonce_info"]
        if "description" in nonce_info:
            print(f"  Beskrivning: {nonce_info['description']}")
        if "warning" in nonce_info:
            print(f"  ⚠️ Varning: {nonce_info['warning']}")
    else:
        print("  Ingen nonce-information hittad i dokumentationen.")

    # Visa rekommendationer
    recommendations = scraper.get_auth_recommendations()
    print("\n✅ REST Autentiseringsrekommendationer:")
    if "rest" in recommendations:
        rest_rec = recommendations["rest"]

        if "headers" in rest_rec and rest_rec["headers"]:
            print("  Headers:")
            for key, value in rest_rec["headers"].items():
                print(f"    - {key}: {value}")

        if "nonce_generation" in rest_rec and rest_rec["nonce_generation"]:
            print(f"  Nonce-generering: {rest_rec['nonce_generation']}")

        if "message_format" in rest_rec and rest_rec["message_format"]:
            print(f"  Message-format: {rest_rec['message_format']}")

        if "signature_generation" in rest_rec and rest_rec["signature_generation"]:
            print(f"  Signatur-generering: {rest_rec['signature_generation']}")
    else:
        print("  Inga rekommendationer tillgängliga.")

    # Visa kodexempel
    examples = scraper.generate_auth_code_examples()
    print("\n💻 REST Autentiseringskodexempel (Python):")
    if (
        "rest" in examples
        and "python" in examples["rest"]
        and "build_auth_headers" in examples["rest"]["python"]
    ):
        print(f"```python\n{examples['rest']['python']['build_auth_headers']}\n```")
    else:
        print("  Inga kodexempel tillgängliga.")


def display_ws_auth_info():
    """
    Visar information om WebSocket API autentisering.
    """
    print("\n=== WebSocket API Authentication Information ===\n")

    # Skapa en instans av BitfinexAuthScraper
    scraper = BitfinexAuthScraper()

    # Hämta WebSocket autentiseringsinformation
    ws_info = scraper.fetch_ws_auth_info()

    # Visa autentiseringsparametrar
    print("📝 WebSocket Autentiseringsparametrar:")
    if "auth_parameters" in ws_info and ws_info["auth_parameters"]:
        print("  | Field | Type | Description |")
        print("  |-------|------|-------------|")
        for param in ws_info["auth_parameters"]:
            print(
                f"  | {param.get('field', 'N/A')} | {param.get('type', 'N/A')} | {param.get('description', 'N/A')} |"
            )
    else:
        print("  Inga autentiseringsparametrar hittade i dokumentationen.")

    # Visa nonce-information
    print("\n⏱️ WebSocket Nonce-information:")
    if "nonce_info" in ws_info and ws_info["nonce_info"]:
        nonce_info = ws_info["nonce_info"]
        if "description" in nonce_info:
            print(f"  Beskrivning: {nonce_info['description']}")
        if "warning" in nonce_info:
            print(f"  ⚠️ Varning: {nonce_info['warning']}")
    else:
        print("  Ingen nonce-information hittad i dokumentationen.")

    # Visa exempel-länkar
    print("\n🔗 WebSocket Exempel-länkar:")
    if "examples" in ws_info and ws_info["examples"]:
        for example in ws_info["examples"]:
            print(
                f"  - [{example.get('title', 'N/A')}]({example.get('link', 'N/A')}) ({example.get('language', 'N/A')})"
            )
    else:
        print("  Inga exempel-länkar hittade i dokumentationen.")

    # Visa rekommendationer
    recommendations = scraper.get_auth_recommendations()
    print("\n✅ WebSocket Autentiseringsrekommendationer:")
    if "websocket" in recommendations:
        ws_rec = recommendations["websocket"]

        if "payload_format" in ws_rec and ws_rec["payload_format"]:
            print("  Payload-format:")
            for key, value in ws_rec["payload_format"].items():
                print(f"    - {key}: {value}")

        if "nonce_generation" in ws_rec and ws_rec["nonce_generation"]:
            print(f"  Nonce-generering: {ws_rec['nonce_generation']}")

        if "message_format" in ws_rec and ws_rec["message_format"]:
            print(f"  Message-format: {ws_rec['message_format']}")

        if "signature_generation" in ws_rec and ws_rec["signature_generation"]:
            print(f"  Signatur-generering: {ws_rec['signature_generation']}")
    else:
        print("  Inga rekommendationer tillgängliga.")

    # Visa kodexempel
    examples = scraper.generate_auth_code_examples()
    print("\n💻 WebSocket Autentiseringskodexempel (Python):")
    if (
        "websocket" in examples
        and "python" in examples["websocket"]
        and "build_ws_auth_payload" in examples["websocket"]["python"]
    ):
        print(
            f"```python\n{examples['websocket']['python']['build_ws_auth_payload']}\n```"
        )
    else:
        print("  Inga kodexempel tillgängliga.")


def compare_auth_implementations():
    """
    Jämför dokumentationen med nuvarande implementationer.
    """
    print("\n=== Jämförelse med Nuvarande Implementationer ===\n")

    # Hämta rekommendationer från scrapern
    scraper = BitfinexAuthScraper()
    recommendations = scraper.get_auth_recommendations()

    # Importera nuvarande implementationer
    from rest.auth import build_auth_headers
    from ws.auth import build_ws_auth_payload

    # Jämför REST implementationen
    print("🔄 REST Autentiseringsjämförelse:")
    print(
        f"  Rekommenderad nonce-generering: {recommendations['rest']['nonce_generation']}"
    )
    print(
        f"  Rekommenderat message-format: {recommendations['rest']['message_format']}"
    )
    print("  Nuvarande implementation:")
    print(f"```python\n{build_auth_headers.__doc__}\n```")

    # Jämför WebSocket implementationen
    print("\n🔄 WebSocket Autentiseringsjämförelse:")
    print(
        f"  Rekommenderad nonce-generering: {recommendations['websocket']['nonce_generation']}"
    )
    print(
        f"  Rekommenderat message-format: {recommendations['websocket']['message_format']}"
    )
    print("  Nuvarande implementation:")
    print(f"```python\n{build_ws_auth_payload.__doc__}\n```")

    # Analysera skillnader
    print("\n⚖️ Analys av skillnader:")

    # REST skillnader
    rest_diffs = []
    if "mikrosekunder" in recommendations["rest"][
        "nonce_generation"
    ] and "timestamp() * 1_000_000" not in str(build_auth_headers):
        rest_diffs.append(
            "REST nonce bör genereras med mikrosekunder (timestamp * 1_000_000)"
        )

    if not rest_diffs:
        print("  ✅ REST implementation följer rekommendationerna")
    else:
        print("  ⚠️ REST implementation har skillnader:")
        for diff in rest_diffs:
            print(f"    - {diff}")

    # WebSocket skillnader
    ws_diffs = []
    if "millisekunder" in recommendations["websocket"][
        "nonce_generation"
    ] and "timestamp() * 1000" not in str(build_ws_auth_payload):
        ws_diffs.append(
            "WebSocket nonce bör genereras med millisekunder (timestamp * 1000)"
        )

    if not ws_diffs:
        print("  ✅ WebSocket implementation följer rekommendationerna")
    else:
        print("  ⚠️ WebSocket implementation har skillnader:")
        for diff in ws_diffs:
            print(f"    - {diff}")


def main():
    """
    Huvudfunktion för att visa autentiseringsinformation.
    """
    print("🔒 Genesis Trading Bot - Authentication Examples")
    print("==============================================")

    # Visa REST autentiseringsinformation
    display_rest_auth_info()

    # Visa WebSocket autentiseringsinformation
    display_ws_auth_info()

    # Jämför med nuvarande implementationer
    compare_auth_implementations()

    print("\n✅ Exempel slutförda!")


if __name__ == "__main__":
    main()

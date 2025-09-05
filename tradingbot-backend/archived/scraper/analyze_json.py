import json
import os
from typing import Any, Dict, List


def analyze_json_file(file_path: str) -> Dict[str, Any]:
    """
    Analyserar en JSON-fil och returnerar metadata

    Args:
        file_path: Sökväg till JSON-filen

    Returns:
        Dictionary med metadata om filen
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            size_kb = len(content) / 1024

            data = json.loads(content)

            metadata = {
                "file_name": os.path.basename(file_path),
                "size_kb": round(size_kb, 2),
                "type": type(data).__name__,
                "structure": {},
            }

            if isinstance(data, dict):
                metadata["structure"] = {
                    "keys": list(data.keys()),
                    "total_keys": len(data),
                }
            elif isinstance(data, list):
                metadata["structure"] = {
                    "length": len(data),
                    "sample": data[0] if data else None,
                }
                if data:
                    if all(isinstance(x, dict) for x in data):
                        # Om alla element är dictionaries, visa nycklar från första elementet
                        metadata["structure"]["item_keys"] = list(data[0].keys())

            return metadata

    except Exception as e:
        return {"file_name": os.path.basename(file_path), "error": str(e)}


def analyze_directory(directory: str) -> List[Dict[str, Any]]:
    """
    Analyserar alla JSON-filer i en katalog

    Args:
        directory: Sökväg till katalogen

    Returns:
        Lista med metadata för varje fil
    """
    results = []

    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            file_path = os.path.join(directory, filename)
            metadata = analyze_json_file(file_path)
            results.append(metadata)

    return results


def format_metadata(metadata: List[Dict[str, Any]]) -> str:
    """
    Formaterar metadata till läsbar text

    Args:
        metadata: Lista med metadata

    Returns:
        Formaterad text
    """
    output = []

    for item in metadata:
        output.append(f"\n## {item['file_name']}")
        output.append(f"- Storlek: {item['size_kb']} KB")

        if "error" in item:
            output.append(f"- Error: {item['error']}")
            continue

        output.append(f"- Typ: {item['type']}")

        if item["type"] == "dict":
            output.append("- Struktur:")
            output.append("  - Nycklar:")
            for key in item["structure"]["keys"]:
                output.append(f"    - {key}")
            output.append(f"  - Totalt antal nycklar: {item['structure']['total_keys']}")

        elif item["type"] == "list":
            output.append("- Struktur:")
            output.append(f"  - Längd: {item['structure']['length']}")
            if "item_keys" in item["structure"]:
                output.append("  - Element innehåller följande nycklar:")
                for key in item["structure"]["item_keys"]:
                    output.append(f"    - {key}")
            if item["structure"]["sample"]:
                output.append("  - Exempel på element:")
                output.append(f"    ```json\n    {json.dumps(item['structure']['sample'], indent=2)}\n    ```")

    return "\n".join(output)


def main():
    directory = "cache/bitfinex_docs"
    results = analyze_directory(directory)

    # Sortera efter filstorlek
    results.sort(key=lambda x: x.get("size_kb", 0), reverse=True)

    # Skapa rapport
    report = "# JSON-filanalys\n"
    report += "\nAnalys av JSON-filer i cache/bitfinex_docs:\n"
    report += format_metadata(results)

    # Spara rapport
    with open("cache/bitfinex_docs/JSON_ANALYSIS.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("Analys slutförd! Se JSON_ANALYSIS.md för detaljer.")


if __name__ == "__main__":
    main()

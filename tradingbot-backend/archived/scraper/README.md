# JSON Extractor

Ett verktyg för att extrahera JSON-objekt och arrays från HTML-filer.

## Funktioner

- Extraherar JSON-objekt och arrays från HTML-filer
- Hanterar HTML-entities korrekt
- Stöd för nästlade JSON-strukturer
- Filtrerar bort meningslös JSON (t.ex. arrays med bara nummer)
- Sparar extraherade JSON-objekt i separata filer
- Detaljerad loggning av processen

## Installation

Verktyget är en del av Genesis Trading Bot-projektet. Inga extra beroenden behövs utöver de som redan finns i `requirements.txt`.

## Användning

### Som modul

```python
from scraper.json_extractor import JsonExtractor

# Skapa en extractor
extractor = JsonExtractor(cache_dir="path/to/cache")

# Bearbeta en enskild fil
results = extractor.process_file("example.html")

# Bearbeta alla filer i cache-katalogen
all_results = extractor.process_all_files()
```

### Som script

```bash
python -m scraper.json_extractor
```

## Exempel

### Extrahera JSON från HTML

```python
html_content = '''
<script>
    {"test": "data"}
</script>
'''

extractor = JsonExtractor()
results = extractor.extract_json_from_html(html_content)
print(results)  # [{"test": "data"}]
```

### Hantera HTML-entities

```python
html_content = '''
<script>
    {"special": "&quot;quoted&quot;"}
</script>
'''

extractor = JsonExtractor()
results = extractor.extract_json_from_html(html_content)
print(results)  # [{"special": "quoted"}]
```

### Extrahera JSON-arrays

```python
html_content = '''
<script>
    [
        {"item": 1},
        {"item": 2}
    ]
</script>
'''

extractor = JsonExtractor()
results = extractor.extract_json_from_html(html_content)
print(results)  # [[{"item": 1}, {"item": 2}]]
```

## Filtrering

Verktyget filtrerar automatiskt bort:
- Tomma objekt och arrays
- Arrays som bara innehåller nummer
- Ogiltig JSON
- HTML och annan text som inte är JSON

## Loggning

Verktyget använder Pythons inbyggda `logging`-modul för att logga:
- Information om bearbetade filer
- Extraherade JSON-objekt
- Fel och varningar
- Debug-information vid behov

## Tester

Kör testerna med:

```bash
python -m pytest tests/test_json_extractor.py -v
```

## Begränsningar

- Hanterar för närvarande bara JSON-objekt och arrays
- Filtrerar bort arrays som bara innehåller nummer
- Kräver att JSON-objekt är korrekt formaterade
- Stöder inte kommentarer i JSON

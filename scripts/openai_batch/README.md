# OpenAI Batch – snabbstart

Den här mappen innehåller en minimal uppsättning för att köra OpenAI Batch‑jobb via Python‑skript.

## Innehåll
- `requirements.txt` – beroenden
- `env.example` – exempelmiljö (kopiera till `.env`)
- `batch_examples.jsonl` – exempel på batch‑inputs i JSONL (Chat Completions)
- `batch_examples_responses.jsonl` – exempel för Responses‑API
- `submit_batch.py` – skickar ett batch‑jobb
- `poll_batch.py` – hämtar status och laddar ner resultat

## Installation
```powershell
cd scripts/openai_batch
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

## Konfiguration
1. Skapa en `.env` baserat på `env.example` och fyll i din nyckel:
```dotenv
OPENAI_API_KEY=sk-...din-nyckel...
OPENAI_BATCH_INPUT_FILE=batch_examples.jsonl
OPENAI_BATCH_ENDPOINT=/v1/chat/completions
OPENAI_BATCH_COMPLETION_WINDOW=24h
# valfritt: standardmodell att override:a med
# OPENAI_BATCH_MODEL=gpt-4o-mini
```
2. Alternativt kan du exportera env‑variabler direkt i PowerShell innan körning:
```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_BATCH_INPUT_FILE = "batch_examples.jsonl"
$env:OPENAI_BATCH_ENDPOINT = "/v1/chat/completions"
$env:OPENAI_BATCH_COMPLETION_WINDOW = "24h"
# valfritt
# $env:OPENAI_BATCH_MODEL = "gpt-4o-mini"
```

## Körning
- Chat Completions (t.ex. gpt‑4o‑mini):
```powershell
python submit_batch.py --input batch_examples.jsonl --endpoint /v1/chat/completions --window 24h --desc "demo-chat"
```
- Responses‑API med `gpt-5-chat-latest`:
```powershell
python submit_batch.py --input batch_examples_responses.jsonl --endpoint /v1/responses --window 24h --desc "demo-gpt5"
```
- Modell‑override (gäller båda formaten; ändrar `body.model` innan uppladdning):
```powershell
python submit_batch.py --input batch_examples_responses.jsonl --endpoint /v1/responses --window 24h --override-model gpt-5-chat-latest --desc "demo-override"
```
- Polla och hämta resultat (anger batch‑ID som skapades):
```powershell
python poll_batch.py --batch-id bat_12345 --out results
```

## Noteringar
- `batch_examples.jsonl` (Chat Completions) och `batch_examples_responses.jsonl` (Responses) har olika schema i `body`.
- `--override-model` skriver temporärt om modellnamn innan uppladdning. Du ansvarar för att formatet (messages vs input) matchar vald endpoint.
- Skripten använder OpenAI Python SDK v1 och hanterar fel, backoff och nedladdning av output/error‑filer.
- Dokumentation: `https://platform.openai.com/docs/guides/batch` och `https://platform.openai.com/docs/models/gpt-5-chat-latest`.

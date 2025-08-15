# OpenAI Batch – snabbstart

Den här mappen innehåller en minimal uppsättning för att köra OpenAI Batch‑jobb via Python‑skript.

## Innehåll
- `requirements.txt` – beroenden
- `env.example` – exempelmiljö (kopiera till `.env`)
- `batch_examples.jsonl` – exempel på batch‑inputs i JSONL
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
- Skicka batch (utan override):
```powershell
python submit_batch.py --input $env:OPENAI_BATCH_INPUT_FILE --endpoint $env:OPENAI_BATCH_ENDPOINT --window $env:OPENAI_BATCH_COMPLETION_WINDOW --desc "demo-batch"
```
- Skicka batch med modell‑override (t.ex. "gpt5-high-fast" om ditt konto har access):
```powershell
python submit_batch.py --input batch_examples.jsonl --endpoint /v1/chat/completions --window 24h --override-model gpt5-high-fast --desc "demo-gpt5"
```
- Polla och hämta resultat (anger batch‑ID som skapades):
```powershell
python poll_batch.py --batch-id bat_12345 --out results
```

## Noteringar
- `batch_examples.jsonl` visar officiellt batch‑format (en rad per request) för Chat Completions‑endpoint.
- `--override-model` skriver temporärt om varje rad till vald modell innan uppladdning.
- Skripten använder OpenAI Python SDK v1 och hanterar fel, backoff och nedladdning av output/error‑filer.
- Dokumentation: `https://platform.openai.com/docs/guides/batch`.

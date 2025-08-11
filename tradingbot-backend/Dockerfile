FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/

# Skapa venv och installera beroenden
RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Kopiera venv från builder
COPY --from=builder /opt/venv /opt/venv

# Lägg till icke-root användare
RUN useradd -ms /bin/bash appuser

# Kopiera applikationskod
COPY . /app
# Exkludera tunga legacy-dokument vid build genom .dockerignore i repo-roten
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python - <<'PY'
import urllib.request, sys
try:
    urllib.request.urlopen('http://localhost:8000/health', timeout=3)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]



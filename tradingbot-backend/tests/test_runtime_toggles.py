"""
AI Change: Lägg till basala tester för runtime-toggles endpoints.
Verifierar att GET/POST /api/v2/mode/dry-run och /api/v2/mode/autotrade
fungerar och speglar värden konsekvent.

Körs mot FastAPI appen via httpx.AsyncClient och asgi transport.
"""

import asyncio
import os
import pytest
from typing import AsyncIterator

import httpx


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    # Tillåt asyncio backend
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    # Se till att autentisering inte krävs i lokal test
    os.environ.setdefault("AUTH_REQUIRED", "False")

    # Importera app först efter env-override
    from main import app  # type: ignore

    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_mode_dry_run_toggle(client: httpx.AsyncClient) -> None:
    # Läs initialt värde
    r1 = await client.get("/api/v2/mode/dry-run", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = r1.json().get("dry_run_enabled")

    # Sätt motsatt värde
    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/dry-run",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert r2.json().get("dry_run_enabled") == target

    # Läs igen och verifiera
    r3 = await client.get("/api/v2/mode/dry-run", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert r3.json().get("dry_run_enabled") == target


@pytest.mark.anyio
async def test_mode_autotrade_toggle(client: httpx.AsyncClient) -> None:
    # Läs initialt värde
    r1 = await client.get("/api/v2/mode/autotrade", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = r1.json().get("autotrade_enabled")

    # Sätt motsatt värde
    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/autotrade",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert r2.json().get("autotrade_enabled") == target

    # Läs igen och verifiera
    r3 = await client.get("/api/v2/mode/autotrade", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert r3.json().get("autotrade_enabled") == target


@pytest.mark.anyio
async def test_mode_ws_strategy_toggle(client: httpx.AsyncClient) -> None:
    r1 = await client.get("/api/v2/mode/ws-strategy", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = r1.json().get("ws_strategy_enabled")

    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/ws-strategy",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert r2.json().get("ws_strategy_enabled") == target

    r3 = await client.get("/api/v2/mode/ws-strategy", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert r3.json().get("ws_strategy_enabled") == target


@pytest.mark.anyio
async def test_mode_validation_warmup_toggle(client: httpx.AsyncClient) -> None:
    r1 = await client.get("/api/v2/mode/validation-warmup", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = r1.json().get("validation_on_start")

    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/validation-warmup",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert r2.json().get("validation_on_start") == target

    r3 = await client.get("/api/v2/mode/validation-warmup", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert r3.json().get("validation_on_start") == target


@pytest.mark.anyio
async def test_mode_prob_model_toggle(client: httpx.AsyncClient) -> None:
    r1 = await client.get("/api/v2/mode/prob-model", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = r1.json().get("prob_model_enabled")

    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/prob-model",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert r2.json().get("prob_model_enabled") == target

    r3 = await client.get("/api/v2/mode/prob-model", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert r3.json().get("prob_model_enabled") == target


@pytest.mark.anyio
async def test_mode_ws_connect_on_start_toggle(client: httpx.AsyncClient) -> None:
    r1 = await client.get("/api/v2/mode/ws-connect-on-start", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = r1.json().get("ws_connect_on_start")

    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/ws-connect-on-start",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert r2.json().get("ws_connect_on_start") == target

    r3 = await client.get("/api/v2/mode/ws-connect-on-start", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert r3.json().get("ws_connect_on_start") == target


@pytest.mark.anyio
async def test_mode_scheduler_toggle(client: httpx.AsyncClient) -> None:
    r1 = await client.get("/api/v2/mode/scheduler", headers={"Authorization": "Bearer dev"})
    assert r1.status_code == 200
    initial = bool(r1.json().get("scheduler_running"))

    target = not bool(initial)
    r2 = await client.post(
        "/api/v2/mode/scheduler",
        headers={"Authorization": "Bearer dev"},
        json={"enabled": target},
    )
    assert r2.status_code == 200
    assert bool(r2.json().get("scheduler_running")) == target

    r3 = await client.get("/api/v2/mode/scheduler", headers={"Authorization": "Bearer dev"})
    assert r3.status_code == 200
    assert bool(r3.json().get("scheduler_running")) == target

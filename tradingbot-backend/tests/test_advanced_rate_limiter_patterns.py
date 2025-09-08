import os

import pytest

from config.settings import Settings
from utils.advanced_rate_limiter import AdvancedRateLimiter, EndpointType


def test_rate_limit_patterns_classification(monkeypatch):
    monkeypatch.setenv(
        "RATE_LIMIT_PATTERNS",
        "^auth/w/=>PRIVATE_TRADING;^auth/r/positions=>PRIVATE_ACCOUNT;^auth/r/wallets=>PRIVATE_ACCOUNT;^auth/r/info/margin=>PRIVATE_MARGIN;^(ticker|candles|book|trades)=>PUBLIC_MARKET",
    )
    # Ny Settings-instans plockar upp env
    s = Settings()
    limiter = AdvancedRateLimiter(settings=s)

    assert limiter._classify_endpoint("auth/w/order/submit") == EndpointType.PRIVATE_TRADING
    assert limiter._classify_endpoint("auth/r/positions") == EndpointType.PRIVATE_ACCOUNT
    assert limiter._classify_endpoint("auth/r/wallets") == EndpointType.PRIVATE_ACCOUNT
    assert limiter._classify_endpoint("auth/r/info/margin/base") == EndpointType.PRIVATE_MARGIN
    assert limiter._classify_endpoint("ticker/tBTCUSD") == EndpointType.PUBLIC_MARKET

    # Okänd privat läses som PRIVATE_ACCOUNT via default-logik
    assert limiter._classify_endpoint("auth/r/info/user") == EndpointType.PRIVATE_ACCOUNT


def test_rate_limit_export_metrics(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PATTERNS", "^(ticker|candles)=>PUBLIC_MARKET")
    s = Settings()
    limiter = AdvancedRateLimiter(settings=s)
    # Export ska inte kasta och fylla counters
    limiter.export_metrics()
    from services.metrics import metrics_store

    counters = metrics_store.get("counters", {})
    assert "limiter_bucket_tokens" in counters
    assert "limiter_bucket_utilization_percent" in counters

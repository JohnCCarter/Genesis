"""
JSON Optimizer - Optimering av JSON parsing och serialisering.

Implementerar:
- Snabbare JSON parsing med orjson
- Schema-validering
- Caching av parsed data
- Streaming JSON parsing
- Memory-efficient serialisering
"""

import json
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import orjson
from pydantic import BaseModel, ValidationError

from utils.logger import get_logger

logger = get_logger(__name__)


class JSONOptimizer:
    """Optimizer för JSON-hantering."""

    def __init__(self, use_orjson: bool = True, enable_cache: bool = True):
        self.use_orjson = use_orjson
        self.enable_cache = enable_cache
        self.cache_hits = 0
        self.cache_misses = 0

        # Testa orjson tillgänglighet
        if use_orjson:
            try:
                orjson.loads('{"test": "data"}')
                logger.info("✅ orjson tillgänglig för snabb JSON parsing")
            except ImportError:
                logger.warning("⚠️ orjson inte tillgänglig, använder standard json")
                self.use_orjson = False

    def loads(self, data: str | bytes) -> Any:
        """
        Snabb JSON parsing.

        Args:
            data: JSON data som string eller bytes

        Returns:
            Parsed JSON data
        """
        try:
            if self.use_orjson:
                return orjson.loads(data)
            else:
                return json.loads(data)
        except Exception as e:
            logger.error(f"❌ JSON parsing fel: {e}")
            raise

    def dumps(self, obj: Any, **kwargs) -> str:
        """
        Snabb JSON serialisering.

        Args:
            obj: Objekt att serialisera
            **kwargs: Extra parametrar för json.dumps

        Returns:
            JSON string
        """
        try:
            if self.use_orjson:
                # orjson returnerar bytes, konvertera till string
                return orjson.dumps(obj, **kwargs).decode("utf-8")
            else:
                return json.dumps(obj, **kwargs)
        except Exception as e:
            logger.error(f"❌ JSON serialisering fel: {e}")
            raise

    @lru_cache(maxsize=1000)
    def parse_cached(self, data: str) -> Any:
        """
        Cached JSON parsing för ofta använd data.

        Args:
            data: JSON string

        Returns:
            Parsed JSON data
        """
        if not self.enable_cache:
            return self.loads(data)

        try:
            result = self.loads(data)
            self.cache_hits += 1
            return result
        except Exception as e:
            self.cache_misses += 1
            logger.error(f"❌ Cached JSON parsing fel: {e}")
            raise

    def validate_schema(self, data: Any, schema: BaseModel) -> Any:
        """
        Validera data mot Pydantic schema.

        Args:
            data: Data att validera
            schema: Pydantic schema

        Returns:
            Validerad data
        """
        try:
            if isinstance(data, dict):
                return schema.model_validate(data)
            else:
                return schema.model_validate(data)
        except ValidationError as e:
            logger.error(f"❌ Schema validering fel: {e}")
            raise

    def parse_streaming(self, data_stream: list[str]) -> list[Any]:
        """
        Streaming JSON parsing för stora datamängder.

        Args:
            data_stream: Lista med JSON strings

        Returns:
            Lista med parsed data
        """
        results = []

        for i, json_str in enumerate(data_stream):
            try:
                parsed = self.loads(json_str)
                results.append(parsed)
            except Exception as e:
                logger.warning(f"⚠️ Fel vid parsing av item {i}: {e}")
                continue

        return results

    def optimize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Optimera dictionary för JSON serialisering.

        Args:
            data: Dictionary att optimera

        Returns:
            Optimerad dictionary
        """
        optimized = {}

        for key, value in data.items():
            # Ta bort None-värden
            if value is None:
                continue

            # Konvertera numeriska strängar till numbers
            if isinstance(value, str):
                try:
                    if "." in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass

            # Rekursiv optimering för nested dictionaries
            elif isinstance(value, dict):
                value = self.optimize_dict(value)

            # Optimera listor
            elif isinstance(value, list):
                value = [self.optimize_dict(item) if isinstance(item, dict) else item for item in value]

            optimized[key] = value

        return optimized

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Hämta cache-statistik.

        Returns:
            Dict med cache-statistik
        """
        if not self.enable_cache:
            return {"cache_enabled": False}

        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_enabled": True,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate_percent": hit_rate,
        }

    def clear_cache(self) -> None:
        """Rensa cache."""
        if self.enable_cache:
            self.parse_cached.cache_clear()
            self.cache_hits = 0
            self.cache_misses = 0
            logger.info("🗑️ JSON cache rensad")


class CandleDataOptimizer:
    """Specialiserad optimizer för candle data."""

    def __init__(self, json_optimizer: JSONOptimizer | None = None):
        self.json_optimizer = json_optimizer or JSONOptimizer()

    def parse_candles(self, candle_data: list[list[Any]]) -> list[dict[str, Any]]:
        """
        Optimera parsing av candle data.

        Args:
            candle_data: Raw candle data från Bitfinex

        Returns:
            Lista med optimerade candle dictionaries
        """
        optimized_candles = []

        for candle in candle_data:
            try:
                # Bitfinex candle format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
                optimized_candle = {
                    "timestamp": int(candle[0]),
                    "open": float(candle[1]),
                    "close": float(candle[2]),
                    "high": float(candle[3]),
                    "low": float(candle[4]),
                    "volume": float(candle[5]),
                }
                optimized_candles.append(optimized_candle)
            except (IndexError, ValueError) as e:
                logger.warning(f"⚠️ Fel vid parsing av candle: {e}")
                continue

        return optimized_candles

    def batch_parse_candles(self, candle_batches: list[list[list[Any]]]) -> list[dict[str, Any]]:
        """
        Batch-parse candle data för bättre prestanda.

        Args:
            candle_batches: Lista med candle batches

        Returns:
            Sammanfogad lista med optimerade candles
        """
        all_candles = []

        for batch in candle_batches:
            batch_candles = self.parse_candles(batch)
            all_candles.extend(batch_candles)

        return all_candles


class OrderDataOptimizer:
    """Specialiserad optimizer för order data."""

    def __init__(self, json_optimizer: JSONOptimizer | None = None):
        self.json_optimizer = json_optimizer or JSONOptimizer()

    def parse_order(self, order_data: list[Any]) -> dict[str, Any]:
        """
        Optimera parsing av order data.

        Args:
            order_data: Raw order data från Bitfinex

        Returns:
            Optimerad order dictionary
        """
        try:
            # Bitfinex order format: [ID, GID, CID, SYMBOL, MTS_CREATE, MTS_UPDATE, AMOUNT, AMOUNT_ORIG, TYPE, TYPE_PREV, MTS_TIF, FLAGS, STATUS, PRICE, PRICE_AVG, PRICE_TRAILING, PRICE_AUX_LIMIT, NOTIFY, HIDDEN, PLACED_ID, ROUTING, META]
            optimized_order = {
                "id": int(order_data[0]),
                "gid": int(order_data[1]) if order_data[1] else None,
                "cid": int(order_data[2]) if order_data[2] else None,
                "symbol": str(order_data[3]),
                "mts_create": int(order_data[4]),
                "mts_update": int(order_data[5]),
                "amount": float(order_data[6]),
                "amount_orig": float(order_data[7]),
                "type": str(order_data[8]),
                "type_prev": str(order_data[9]) if order_data[9] else None,
                "mts_tif": int(order_data[10]) if order_data[10] else None,
                "flags": int(order_data[11]) if order_data[11] else None,
                "status": str(order_data[12]),
                "price": float(order_data[13]),
                "price_avg": float(order_data[14]),
                "price_trailing": float(order_data[15]) if order_data[15] else None,
                "price_aux_limit": float(order_data[16]) if order_data[16] else None,
                "notify": bool(order_data[17]) if order_data[17] is not None else False,
                "hidden": bool(order_data[18]) if order_data[18] is not None else False,
                "placed_id": int(order_data[19]) if order_data[19] else None,
                "routing": str(order_data[20]) if order_data[20] else None,
                "meta": order_data[21] if order_data[21] else {},
            }
            return optimized_order
        except (IndexError, ValueError) as e:
            logger.error(f"❌ Fel vid parsing av order: {e}")
            raise

    def parse_orders_batch(self, orders_data: list[list[Any]]) -> list[dict[str, Any]]:
        """
        Batch-parse order data.

        Args:
            orders_data: Lista med order data

        Returns:
            Lista med optimerade order dictionaries
        """
        optimized_orders = []

        for order_data in orders_data:
            try:
                optimized_order = self.parse_order(order_data)
                optimized_orders.append(optimized_order)
            except Exception as e:
                logger.warning(f"⚠️ Fel vid parsing av order batch: {e}")
                continue

        return optimized_orders


# Globala instanser
json_optimizer = JSONOptimizer()
candle_optimizer = CandleDataOptimizer(json_optimizer)
order_optimizer = OrderDataOptimizer(json_optimizer)


def benchmark_json_parsing(data: str, iterations: int = 1000) -> dict[str, float]:
    """
    Benchmark JSON parsing prestanda.

    Args:
        data: JSON string att testa
        iterations: Antal iterationer

    Returns:
        Dict med benchmark resultat
    """
    results = {}

    # Test standard json
    start_time = time.time()
    for _ in range(iterations):
        json.loads(data)
    standard_time = time.time() - start_time
    results["standard_json"] = standard_time

    # Test orjson
    try:
        start_time = time.time()
        for _ in range(iterations):
            orjson.loads(data)
        orjson_time = time.time() - start_time
        results["orjson"] = orjson_time
        results["speedup"] = standard_time / orjson_time
    except ImportError:
        results["orjson"] = float("inf")
        results["speedup"] = float("inf")

    return results

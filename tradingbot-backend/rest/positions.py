"""
Positions Service - TradingBot Backend

Denna modul hanterar positionsinformation från Bitfinex API.
Inkluderar funktioner för att hämta aktiva positioner och hantera positioner.
"""

import asyncio
import time
        return [position for position in positions if position.is_short]

    async def close_position(self, symbol: str) -> dict[str, Any]:
        """
        Stänger en margin-position genom att skicka en reduce-only market-order i motsatt riktning.
        """
        try:
                        raise httpx.HTTPStatusError("server busy", request=response.request, response=response)
                    response.raise_for_status()
                    result = response.json()
                    break
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(0, 0.1)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise
                logger.info(f"✅ REST API: Reduce-only order skickad för {symbol}")
                return {
                    "success": True,
                    "message": "Reduce-only submit skickad",
                    "data": result,
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Fel vid stängning av position (HTTP): {e}")
            raise
        except Exception as e:
            logger.error(f"Fel vid stängning av position: {e}")
            raise


# Skapa en global instans av PositionsService
positions_service = PositionsService()


# Exportera funktioner för enkel användning
async def get_positions() -> list[Position]:
    return await positions_service.get_positions()


async def get_position_by_symbol(symbol: str) -> Position | None:
    return await positions_service.get_position_by_symbol(symbol)


async def get_long_positions() -> list[Position]:
    return await positions_service.get_long_positions()


async def get_short_positions() -> list[Position]:
    return await positions_service.get_short_positions()


async def close_position(symbol: str) -> dict[str, Any]:
    return await positions_service.close_position(symbol)

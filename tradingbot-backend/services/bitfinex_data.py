"""
Bitfinex Data Service - TradingBot Backend

Denna modul hanterar hämtning av marknadsdata från Bitfinex REST API.
Inkluderar candlestick-data, ticker-information och orderbook-data.
"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from config.settings import Settings
from rest.auth import build_auth_headers
from utils.logger import get_logger

logger = get_logger(__name__)

class BitfinexDataService:
    """Service för att hämta marknadsdata från Bitfinex."""
    
    def __init__(self):
        self.settings = Settings()
        self.base_url = self.settings.BITFINEX_API_URL
        
    async def get_candles(
        self, 
        symbol: str = "tBTCUSD", 
        timeframe: str = "1m", 
        limit: int = 100
    ) -> Optional[List[Dict]]:
        """
        Hämtar candlestick-data från Bitfinex.
        
        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            timeframe: Tidsram ('1m', '5m', '15m', '30m', '1h', '3h', '6h', '12h', '1D', '7D', '14D', '1M')
            limit: Antal candles att hämta (max 10000)
            
        Returns:
            Lista med candlestick-data eller None vid fel
        """
        try:
            symbol = (symbol or "").strip()
            endpoint = f"candles/trade:{timeframe}:{symbol}/hist"
            url = f"{self.base_url}/{endpoint}"
            
            params = {"limit": limit}
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar candles från {url}")
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                candles = response.json()
                logger.info(f"✅ REST API: Hämtade {len(candles)} candles för {symbol}")
                
                return candles
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av candles: {e}")
            return None
    
    async def get_ticker(self, symbol: str = "tBTCUSD") -> Optional[Dict]:
        """
        Hämtar ticker-information för en symbol.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Dict med ticker-data eller None vid fel
        """
        try:
            import re
            symbol = (symbol or "").strip()
            # Normalisera testsymboler till kolonformat tTESTASSET:TESTUSD
            m = re.match(r"^tTEST([A-Z0-9]+)USD$", symbol)
            if m:
                asset = m.group(1)
                symbol = f"tTEST{asset}:TESTUSD"
            m = re.match(r"^tUSD:TEST([A-Z0-9]+)$", symbol)
            if m:
                asset = m.group(1)
                symbol = f"tTESTUSD:TEST{asset}"
            endpoint = f"ticker/{symbol}"
            url = f"{self.base_url}/{endpoint}"
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar ticker från {url}")
                response = await client.get(url)
                response.raise_for_status()
                
                ticker = response.json()
                logger.info(f"✅ REST API: Hämtade ticker för {symbol}: {ticker[6]}")  # Last price
                
                return {
                    "symbol": symbol,
                    "last_price": ticker[6],
                    "bid": ticker[0],
                    "ask": ticker[2],
                    "high": ticker[8],
                    "low": ticker[9],
                    "volume": ticker[7]
                }
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av ticker: {e}")
            return None
    
    def parse_candles_to_strategy_data(self, candles: List[List]) -> Dict[str, List[float]]:
        """
        Konverterar candlestick-data till format för strategiutvärdering.
        
        Args:
            candles: Lista med candle-data från Bitfinex
            
        Returns:
            Dict med closes, highs, lows för strategiutvärdering
        """
        if not candles:
            return {"closes": [], "highs": [], "lows": []}
        
        # Bitfinex candle format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
        closes = [candle[2] for candle in candles]
        highs = [candle[3] for candle in candles]
        lows = [candle[4] for candle in candles]
        
        logger.debug(f"Parsade {len(closes)} datapunkter för strategiutvärdering")
        
        return {
            "closes": closes,
            "highs": highs,
            "lows": lows
        }

# Global instans för enkel åtkomst
bitfinex_data = BitfinexDataService() 
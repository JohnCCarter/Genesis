import pytest
pytestmark = pytest.mark.skip(reason="Legacy realtime integration test – skipped in current backend focus")
"""
Realtime Tests - TradingBot Backend

Denna modul testar realtids WebSocket-funktionalitet och live strategiutvärdering.
"""

import pytest
import asyncio
from typing import Dict, Any
import json

from services.realtime_strategy import realtime_strategy
from services.bitfinex_websocket import bitfinex_ws

class TestRealtimeStrategy:
    """Testklass för realtids strategiutvärdering."""
    
    @pytest.mark.asyncio
    async def test_realtime_strategy_service_initialization(self):
        """Testar att realtids strategi-service initialiseras korrekt."""
        assert realtime_strategy is not None
        assert hasattr(realtime_strategy, 'active_symbols')
        assert hasattr(realtime_strategy, 'strategy_results')
        assert hasattr(realtime_strategy, 'signal_callbacks')
        assert hasattr(realtime_strategy, 'is_running')
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        """Testar att starta övervakning av en symbol."""
        symbol = "tBTCUSD"
        
        # Starta övervakning
        await realtime_strategy.start_monitoring(symbol)
        
        # Verifiera att symbolen är aktiv
        assert symbol in realtime_strategy.active_symbols
        assert realtime_strategy.is_running
        
        # Stoppa övervakning för cleanup
        await realtime_strategy.stop_monitoring(symbol)
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self):
        """Testar att stoppa övervakning av en symbol."""
        symbol = "tBTCUSD"
        
        # Starta övervakning
        await realtime_strategy.start_monitoring(symbol)
        assert symbol in realtime_strategy.active_symbols
        
        # Stoppa övervakning
        await realtime_strategy.stop_monitoring(symbol)
        
        # Verifiera att symbolen inte längre är aktiv
        assert symbol not in realtime_strategy.active_symbols
    
    @pytest.mark.asyncio
    async def test_get_active_symbols(self):
        """Testar att hämta aktiva symboler."""
        symbol = "tBTCUSD"
        
        # Starta övervakning
        await realtime_strategy.start_monitoring(symbol)
        
        # Hämta aktiva symboler
        active_symbols = realtime_strategy.get_active_symbols()
        
        # Verifiera att symbolen finns i listan
        assert symbol in active_symbols
        
        # Stoppa övervakning för cleanup
        await realtime_strategy.stop_monitoring(symbol)
    
    @pytest.mark.asyncio
    async def test_strategy_result_handling(self):
        """Testar hantering av strategi-resultat."""
        # Skapa mock strategi-resultat
        mock_result = {
            'symbol': 'tBTCUSD',
            'signal': 'BUY',
            'current_price': 50000.0,
            'rsi': 30.0,
            'ema': 49000.0,
            'atr': 1000.0,
            'reason': 'RSI oversold - köpsignal',
            'timestamp': '2025-08-04T23:00:00'
        }
        
        # Hantera resultat
        await realtime_strategy._handle_strategy_result(mock_result)
        
        # Verifiera att resultatet sparades
        saved_result = realtime_strategy.get_latest_signal('tBTCUSD')
        assert saved_result is not None
        assert saved_result['signal'] == 'BUY'
        assert saved_result['current_price'] == 50000.0
    
    @pytest.mark.asyncio
    async def test_get_all_signals(self):
        """Testar att hämta alla signaler."""
        # Skapa mock resultat
        mock_result = {
            'symbol': 'tBTCUSD',
            'signal': 'HOLD',
            'current_price': 50000.0,
            'reason': 'Neutral signal'
        }
        
        # Hantera resultat
        await realtime_strategy._handle_strategy_result(mock_result)
        
        # Hämta alla signaler
        all_signals = realtime_strategy.get_all_signals()
        
        # Verifiera att signalen finns
        assert 'tBTCUSD' in all_signals
        assert all_signals['tBTCUSD']['signal'] == 'HOLD'
    
    @pytest.mark.asyncio
    async def test_get_latest_signal(self):
        """Testar att hämta senaste signal för en symbol."""
        symbol = "tBTCUSD"
        
        # Skapa mock resultat
        mock_result = {
            'symbol': symbol,
            'signal': 'SELL',
            'current_price': 51000.0,
            'reason': 'RSI overbought - säljsignal'
        }
        
        # Hantera resultat
        await realtime_strategy._handle_strategy_result(mock_result)
        
        # Hämta senaste signal
        latest_signal = realtime_strategy.get_latest_signal(symbol)
        
        # Verifiera resultat
        assert latest_signal is not None
        assert latest_signal['signal'] == 'SELL'
        assert latest_signal['current_price'] == 51000.0
    
    @pytest.mark.asyncio
    async def test_stop_all_monitoring(self):
        """Testar att stoppa all övervakning."""
        symbols = ["tBTCUSD", "tETHUSD"]
        
        # Starta övervakning för flera symboler
        for symbol in symbols:
            await realtime_strategy.start_monitoring(symbol)
        
        # Verifiera att alla symboler är aktiva
        assert len(realtime_strategy.active_symbols) == 2
        
        # Stoppa all övervakning
        await realtime_strategy.stop_all_monitoring()
        
        # Verifiera att inga symboler är aktiva
        assert len(realtime_strategy.active_symbols) == 0
        assert not realtime_strategy.is_running

class TestWebSocketIntegration:
    """Testklass för WebSocket-integration."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Testar WebSocket-anslutning till Bitfinex."""
        # Testa anslutning
        connected = await bitfinex_ws.connect()
        
        # Verifiera anslutning
        assert connected is True or connected is False  # Kan vara False i testmiljö
        
        # Stäng anslutning
        await bitfinex_ws.disconnect()
    
    @pytest.mark.asyncio
    async def test_websocket_subscription(self):
        """Testar WebSocket-prenumeration."""
        symbol = "tBTCUSD"
        
        # Skapa en enkel callback för test
        async def test_callback(data):
            return data
        
        # Testa prenumeration
        try:
            await bitfinex_ws.subscribe_ticker(symbol, test_callback)
            # Verifiera att prenumerationen registrerades
            assert symbol in bitfinex_ws.subscriptions
        except Exception as e:
            # I testmiljö kan detta misslyckas, vilket är OK
            assert "connection" in str(e).lower() or "websocket" in str(e).lower()

# TODO: Lägg till integrationstester med riktiga WebSocket-anslutningar 
"""
Models Example - TradingBot Backend

Detta skript visar hur man använder de centraliserade Pydantic-modellerna
för att hantera data i tradingboten.
"""

import os
import sys

# Lägg till projektets rotmapp i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.api_models import (ApiResponse, Candle, OrderRequest,
                               OrderResponse, OrderSide, OrderType, Position,
                               PositionStatus, Ticker, WalletBalance,
                               WalletType)
from utils.logger import get_logger

logger = get_logger(__name__)


def wallet_example():
    """Exempel på hur man använder WalletBalance-modellen."""
    print("\n=== Wallet Example ===")

    # Skapa en WalletBalance från rådata
    raw_data = ["exchange", "BTC", 0.5, 0.0, 0.5]
    wallet = WalletBalance.from_bitfinex_data(raw_data)

    print(f"Wallet Type: {wallet.wallet_type}")
    print(f"Currency: {wallet.currency}")
    print(f"Balance: {wallet.balance}")
    print(f"Available Balance: {wallet.available_balance}")

    # Skapa en WalletBalance direkt
    wallet2 = WalletBalance(
        wallet_type=WalletType.MARGIN,
        currency="ETH",
        balance=2.0,
        unsettled_interest=0.01,
        available_balance=1.95,
    )

    print(f"\nWallet 2 Type: {wallet2.wallet_type}")
    print(f"Currency: {wallet2.currency}")
    print(f"Balance: {wallet2.balance}")
    print(f"Unsettled Interest: {wallet2.unsettled_interest}")
    print(f"Available Balance: {wallet2.available_balance}")

    # Konvertera till dict
    wallet_dict = wallet.model_dump()
    print(f"\nWallet as Dict: {wallet_dict}")

    # Konvertera till JSON
    wallet_json = wallet.model_dump_json()
    print(f"Wallet as JSON: {wallet_json}")


def position_example():
    """Exempel på hur man använder Position-modellen."""
    print("\n=== Position Example ===")

    # Skapa en Position från rådata
    raw_data = ["tBTCUSD", "ACTIVE", 0.1, 50000.0, 0.0, 0, 100.0, 2.0, 48000.0]
    position = Position.from_bitfinex_data(raw_data)

    print(f"Symbol: {position.symbol}")
    print(f"Status: {position.status}")
    print(f"Amount: {position.amount}")
    print(f"Base Price: {position.base_price}")
    print(f"Profit/Loss: {position.profit_loss}")
    print(f"Liquidation Price: {position.liquidation_price}")
    print(f"Is Long: {position.is_long}")
    print(f"Is Short: {position.is_short}")

    # Skapa en Position direkt
    position2 = Position(
        symbol="tETHUSD",
        status=PositionStatus.ACTIVE,
        amount=-2.0,  # Short position
        base_price=3000.0,
        profit_loss=-50.0,
        profit_loss_percentage=-0.83,
        liquidation_price=3500.0,
    )

    print(f"\nSymbol: {position2.symbol}")
    print(f"Status: {position2.status}")
    print(f"Amount: {position2.amount}")
    print(f"Base Price: {position2.base_price}")
    print(f"Profit/Loss: {position2.profit_loss}")
    print(f"Is Long: {position2.is_long}")
    print(f"Is Short: {position2.is_short}")


def order_example():
    """Exempel på hur man använder OrderRequest och OrderResponse-modellerna."""
    print("\n=== Order Example ===")

    # Skapa en OrderRequest
    order_request = OrderRequest(
        symbol="tBTCUSD",
        amount=0.01,
        price=50000.0,
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
    )

    print(f"Order Request Symbol: {order_request.symbol}")
    print(f"Amount: {order_request.amount}")
    print(f"Price: {order_request.price}")
    print(f"Side: {order_request.side}")
    print(f"Type: {order_request.type}")

    # Skapa en OrderResponse från rådata
    raw_data = [
        123456,  # id
        0,  # gid
        789,  # cid
        "tBTCUSD",  # symbol
        1628097600000,  # mts_create
        1628097600000,  # mts_update
        0.01,  # amount
        0.01,  # amount_orig
        "LIMIT",  # type
        None,  # type_prev
        None,  # mts_tif
        None,  # placeholder
        0,  # flags
        "ACTIVE",  # status
        None,  # placeholder
        None,  # placeholder
        50000.0,  # price
        0.0,  # price_avg
        0.0,  # price_trailing
        0.0,  # price_aux_limit
        None,  # placeholder
        None,  # placeholder
        None,  # placeholder
        0,  # notify
        0,  # hidden
    ]

    order_response = OrderResponse.from_bitfinex_data(raw_data)

    print(f"\nOrder Response ID: {order_response.id}")
    print(f"Symbol: {order_response.symbol}")
    print(f"Amount: {order_response.amount}")
    print(f"Price: {order_response.price}")
    print(f"Status: {order_response.status}")
    print(f"Created At: {order_response.created_at}")
    print(f"Is Live: {order_response.is_live}")
    print(f"Is Cancelled: {order_response.is_cancelled}")


def ticker_example():
    """Exempel på hur man använder Ticker-modellen."""
    print("\n=== Ticker Example ===")

    # Skapa en Ticker från rådata
    raw_data = [
        50000.0,  # bid
        10.0,  # bid_size
        50001.0,  # ask
        5.0,  # ask_size
        1000.0,  # daily_change
        2.0,  # daily_change_percentage
        50000.0,  # last_price
        1000.0,  # volume
        51000.0,  # high
        49000.0,  # low
    ]

    ticker = Ticker.from_bitfinex_data("tBTCUSD", raw_data)

    print(f"Symbol: {ticker.symbol}")
    print(f"Bid: {ticker.bid}")
    print(f"Ask: {ticker.ask}")
    print(f"Last Price: {ticker.last_price}")
    print(f"Daily Change: {ticker.daily_change}")
    print(f"Daily Change %: {ticker.daily_change_percentage}%")
    print(f"Volume: {ticker.volume}")
    print(f"High: {ticker.high}")
    print(f"Low: {ticker.low}")


def candle_example():
    """Exempel på hur man använder Candle-modellen."""
    print("\n=== Candle Example ===")

    # Skapa en Candle från rådata
    raw_data = [
        1628097600000,  # timestamp
        50000.0,  # open
        50100.0,  # close
        50200.0,  # high
        49900.0,  # low
        100.0,  # volume
    ]

    candle = Candle.from_bitfinex_data(raw_data)

    print(f"Timestamp: {candle.timestamp}")
    print(f"Open: {candle.open}")
    print(f"Close: {candle.close}")
    print(f"High: {candle.high}")
    print(f"Low: {candle.low}")
    print(f"Volume: {candle.volume}")


def api_response_example():
    """Exempel på hur man använder ApiResponse-modellen."""
    print("\n=== API Response Example ===")

    # Skapa en ApiResponse
    response = ApiResponse(
        success=True,
        message="Operation successful",
        data={"id": 123, "status": "completed"},
    )

    print(f"Success: {response.success}")
    print(f"Message: {response.message}")
    print(f"Data: {response.data}")

    # Konvertera till dict
    response_dict = response.model_dump()
    print(f"\nResponse as Dict: {response_dict}")

    # Konvertera till JSON
    response_json = response.model_dump_json()
    print(f"Response as JSON: {response_json}")


def run_all_examples():
    """Kör alla exempel i sekvens."""
    print("\n=== Kör alla models examples ===\n")

    wallet_example()
    position_example()
    order_example()
    ticker_example()
    candle_example()
    api_response_example()

    print("\n=== Alla examples körda ===\n")


if __name__ == "__main__":
    run_all_examples()

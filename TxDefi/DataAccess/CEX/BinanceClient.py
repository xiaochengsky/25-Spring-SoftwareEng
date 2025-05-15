from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
import threading
import os

load_dotenv(override=True)
class BinanceClient(threading.Thread):
    def __init__(self, api_key: str, api_secret: str, country_code: str):
        threading.Thread.__init__(self, daemon=True)
        self.name = BinanceClient.__name__
        # Initialize Binance Client
        self.client = Client(api_key, api_secret, tld=country_code)
    
    """
    Places a market order to buy a token pair (ticker/USDT) using a specified USDT amount.
    """
    def execute_order(self, symbol: str, usdt_amount: float):
        try:  
            # Get current price for the token pair
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Calculate quantity to buy based on USDT amount
            quantity = usdt_amount / current_price
            
            # Round quantity to match Binance step size rules
            info = self.client.get_symbol_info(symbol)
            step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', info['filters']))['stepSize'])
            quantity = round(quantity - (quantity % step_size), 6)  # Adjust quantity
            
            # Place Market Order
            order = self.client.order_market_buy(
                symbol=symbol,
                quantity=quantity
            )
            
            print("Market Order Successful!")
            print("Order Details:", order)
            
        except BinanceAPIException as e:
            print(f"Error placing market order: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

if __name__ == "__main__":
    # API Credentials (Replace with your API Key and Secret)
    API_KEY = os.getenv('BINANCE_API_KEY', 'your_api_key_here')
    API_SECRET = os.getenv('BINANCE_API_SECRET', 'your_api_secret_here')
    # Parameters
    SYMBOL = "MEUSDT"  # Token pair
    USDT_AMOUNT = 2  # Specify USDT amount to trade
    client = BinanceClient(API_KEY, API_SECRET, 'us')
    # Execute Market Order
    client.execute_order(SYMBOL, USDT_AMOUNT)

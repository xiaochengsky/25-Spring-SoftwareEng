import threading
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
import TxDefi.Data.Globals as globals

class BundleStrategy(AbstractTradingStrategy):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_ui_command], settings)
        self.process_lock = threading.Lock()

    def process_event(self, id: int, event: any):
        with self.process_lock:
            if isinstance(event, Command) and event.command_type == UI_Command.BUY: #Buy the lot
                new_swap_settings = self.original_swap_settings.clone()
                bundled_swap_order = BundledSwapOrder(TradeEventType.BUY, self.token_address, new_swap_settings, self.wallet_settings)
                self.trades_manager.execute(bundled_swap_order, max_tries = 3)                
            if isinstance(event, Command) and event.command_type == UI_Command.SELL_ALL: #Sell the lot
                new_swap_settings = self.original_swap_settings.clone()
                
                for wallet in self.wallet_settings.signer_wallets:
                    amount = self.trades_manager.get_token_account_balance(self.token_address, wallet.get_account_address())
                    wallet.amount_in = amount
                
                bundled_swap_order = BundledSwapOrder(TradeEventType.SELL, self.token_address, new_swap_settings, self.wallet_settings)
                self.trades_manager.execute(bundled_swap_order, max_tries = 3)

                self.set_strategy_complete()

    def load_from_dict(self, strategy_settings: dict[str, any]):
        self.original_swap_settings = SwapOrderSettings.load_from_dict(strategy_settings)
        self.wallet_settings = SignerWalletSettings.load_from_dict(strategy_settings)     
        self.token_address = strategy_settings.get('token_address')

    def load_from_obj(self, obj: object): 
        pass
    
    @classmethod
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"BundleStrategy":
        return BundleStrategy(trades_manager, settings)
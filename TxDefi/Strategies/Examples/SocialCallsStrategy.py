import threading
import concurrent.futures
from TxDefi.Data.TradingDTOs import *
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Utilities.SoundUtils import *
import TxDefi.Data.Globals as globals

class SocialCallsStrategy(AbstractTradingStrategy[CallEvent]):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_ca_call_event], settings)
        self.process_lock = threading.Lock()
        self.sound_utils = SoundUtils()

    def process_event(self, id: int, event: CallEvent):
        with self.process_lock:
            for ca in event.contract_addresses:
                #TODO Add risk assessment logic to see if this token is worth it
                if ca not in self.sniped_tokens:
                    self.sniped_tokens.append(ca)
                    
                    print("Processing auto_buy with " + ca)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        executor.submit(self.auto_buy, (ca))
                        executor.submit(self.sound_utils.play_sound(SoundType.ALERT))   

                    #self.set_strategy_complete() #Uncomment if you only want to do this once

    def auto_buy(self, token_address: str):
        if self.swap_settings:
            order = SwapOrder(TradeEventType.BUY, token_address, self.swap_settings, self.wallet_settings)
            tx_signatures = self.trades_manager.execute(order, max_tries = 3)
            
            #Optional, could estimate what we bought if time is critical; stay tuned for bonus material on this
            token_info = self.trades_manager.get_market_manager().get_token_info(token_address)

            for signature in tx_signatures:
                transaction_info_list = self.trades_manager.get_swap_info(signature, self.wallet_settings.get_default_signer().get_account_address(), 30)
                transaction_info = transaction_info_list[0] if len(transaction_info_list) > 0 else None
                
                if transaction_info and transaction_info.token_balance_change > 0:                
                    #base_token_price = Amount.sol_scaled(abs(transaction_info.sol_balance_change/transaction_info.token_balance_change))
                    #tokens_bought = Amount.tokens_ui(transaction_info.token_balance_change, token_info.token_vault_amount.decimals)                    
                    #print(f"Received Transaction {signature} Base Price: {base_token_price.to_ui()} Tokens: {tokens_bought.to_ui()}") #DELETE
                    transaction_info.print_swap_info()

    def load_from_dict(self, strategy_settings: dict[str, any]):
        self.swap_settings = SwapOrderSettings.load_from_dict(strategy_settings)
        self.wallet_settings = SignerWalletSettings.load_from_dict(strategy_settings)     
        self.sniped_tokens : list[str] = strategy_settings.get('snipe_tokens')       

    def load_from_obj(self, obj: object): 
        pass  
    
    @classmethod
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"SocialCallsStrategy":
        return SocialCallsStrategy(trades_manager, settings)        

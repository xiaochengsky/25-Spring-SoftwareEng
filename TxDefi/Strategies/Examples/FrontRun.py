from datetime import datetime, timezone
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
import TxDefi.Data.Globals as globals
import time

class FrontRun(AbstractTradingStrategy):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [], settings)

    #process a subbed event
    def process_event(self, id: int, event: any):
        if isinstance(event, list):
            for obj in event:
                if isinstance(obj, RetailTransaction) and obj.is_buy:
                    with self.updates_lock:
                        if self.state != StrategyState.COMPLETE:
                            #token_price = self.order_executor.market_manager.get_price(obj.mint_address)
                            #jump_percent = obj.payerPrice/token_price - 1
                            #if jump_percent > 0:
                            market_manager = self.trades_manager.get_market_manager()
                            #token_info = market_manager.monitor_token(obj.mint_address)
                            amount_in = self.swap_order.get_signer_amount()
                            tokens_out = market_manager.get_estimated_tokens(obj.mint_address, amount_in) #Could wait to get the actual amount using the rpc, but that's slower
                          
                            start_time = time.time_ns()
                            self.swap_order.token_address = obj.mint_address
                            tx_signature = self.trades_manager.execute(self.swap_order, 3)
                            end_time = time.time_ns()
                            self.swap_order.order_type = TradeEventType.SELL      
                                   
                            tokens_out.value *= .95 #Reduce 5%
                            self.swap_order.wallet_settings.get_default_signer().amount_in = tokens_out #TODO figure out why attributes not visible on VC
                            self.swap_order.swap_settings = self.swap_settings.clone() #Reinit as settings may have updated
                            tx_signature = self.trades_manager.execute(self.swap_order, 3)
                            self.state = StrategyState.COMPLETE

                            print("1st Operation took " + str(end_time-start_time) + " ns")
                            print("Tried front run on " + obj.tx_signature + " token address " + obj.mint_address)
                            if tx_signature:
                                print(tx_signature + " tx submitted!")                       
                            elif obj.get_type() == TradeEventType.ADD_LIQUIDITY or isinstance(obj, PumpMigration) or isinstance(obj, ExtendedMetadata):
                                utc_now = datetime.now(timezone.utc)
                                print(f"{str(utc_now)}: New token {str(obj.tx_signature)} Event Count: {str(id)}")
                    

    def load_from_dict(self, strategy_settings: dict[str, any]):
        amm_names = strategy_settings.get("amms", [])

        if not amm_names:
            print("FrontRun: No AMMs are configured")
            return
        self.subbed_topics = [globals.topic_amm_program_event]
        
        for amm in amm_names:
            program_name = SupportedPrograms.string_to_enum(amm)

            if program_name:
                #Do something with this
                pass                 
    
        self.swap_settings = SwapOrderSettings.load_from_dict(strategy_settings)
        self.wallet_settings = SignerWalletSettings.load_from_dict(strategy_settings) 

        self.swap_order = BundledSwapOrder(TradeEventType.BUY, "", self.swap_settings.clone(), self.wallet_settings)
        #self.swap_order = SwapOrder(TradeEventType.BUY, "", self.swap_settings, self.wallet_settings)

    def load_from_obj(self, obj: object): 
        pass
    
    @classmethod    
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"FrontRun":
        return FrontRun(trades_manager, settings)

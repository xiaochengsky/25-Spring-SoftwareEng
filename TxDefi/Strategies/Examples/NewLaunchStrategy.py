import threading
from datetime import datetime, timezone
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
import TxDefi.Data.Globals as globals

class NewLaunchStrategy(AbstractTradingStrategy):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_token_alerts], settings)
        self.lock = threading.Lock()
        
    #process a subbed event
    def process_event(self, id: int, event: any):
        #if isinstance(obj, InitMintData) or isinstance(obj, PumpMigration) or isinstance(obj, ExtendedMetadata):
            #utc_now = datetime.now(timezone.utc)
            #print(f"{str(utc_now)}: New token {str(obj.tx_signature)} Event Count: {str(id)}")
        if isinstance(event, ExtendedMetadata) and event.program_type in self.supported_programs:
            with self.lock:
                if self.state != StrategyState.COMPLETE:
                    order = SwapOrder(TradeEventType.BUY, event.token_address, self.swap_settings, self.wallet_settings)
                    order.set_use_signer_amount(True) #Will use defaults if you don't set this
                    
                    #Make Transaction
                    tx_signatures = self.trades_manager.execute(order, 3)

                    if tx_signatures and len(tx_signatures) > 0:
                        print(tx_signatures[0])
                    self.state = StrategyState.COMPLETE #just do this once as a demonstration
            

    def load_from_dict(self, strategy_settings: dict[str, any]):
        amm_names = strategy_settings.get("amms", [])
        self.supported_programs : list[SupportedPrograms] = []

        if not amm_names:
            print("NewLaunchStrategy: No AMMs are configured")
            return
        
        for amm in amm_names:
            program_name = SupportedPrograms.string_to_enum(amm)
            
            if program_name:
                self.supported_programs.append(program_name)

        self.swap_settings = SwapOrderSettings.load_from_dict(strategy_settings)
        self.wallet_settings = SignerWalletSettings.load_from_dict(strategy_settings)
      
    def load_from_obj(self, obj: object):
        pass
    
    @classmethod        
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"NewLaunchStrategy":
        return NewLaunchStrategy(trades_manager, settings)
        

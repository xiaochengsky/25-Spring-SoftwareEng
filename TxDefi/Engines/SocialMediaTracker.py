from abc import abstractmethod
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy

import TxDefi.Data.Globals as globals

class SocialMediaTracker(AbstractTradingStrategy[CallEvent]):
    def __init__(self, trades_manager):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_ca_call_event])

    @abstractmethod
    def process_event(self, id: int, event: CallEvent):
        pass

    def load_from_dict(self, strategy_settings: dict[str, any]): 
        pass

    def load_from_obj(self, obj: object): 
        pass
    
    @classmethod        
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"SocialMediaTracker":
        return SocialMediaTracker(trades_manager, settings)
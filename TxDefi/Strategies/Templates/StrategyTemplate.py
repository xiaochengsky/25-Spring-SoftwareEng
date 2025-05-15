from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
import TxDefi.Data.Globals as globals

class StrategyTemplate(AbstractTradingStrategy):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_ui_command], settings)

    def process_event(self, id: int, event: any):
        pass

    def load_from_dict(self, strategy_settings: dict[str, any]):
        pass

    def load_from_obj(self, obj: object): 
        pass
    
    @classmethod
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"StrategyTemplate":
        return StrategyTemplate(trades_manager, settings)

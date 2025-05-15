import threading

from TxDefi.Data.TradingDTOs import *
from TxDefi.Strategies.PnlTradingStrategy import PnlTradingStrategy
from TxDefi.Strategies.McapTargetStrategy import McapTargetStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Strategies.PnlTradingStrategy import PnlTradingStrategy
import TxDefi.Utilities.ModuleLoader as ModuleLoader

class StrategyFactory:
    def __init__(self, strategies_path: str = ""):
        self.custom_strategies : dict[str, AbstractTradingStrategy] = {} #key=
        self.load_strategies(strategies_path)

    def load_strategies(self, folder_path: str):
        classes = ModuleLoader.find_classes_with_parent_class(folder_path, AbstractTradingStrategy)

        for class_name in classes:
            strategy_class = getattr(classes[class_name], class_name)
            self.add_strategy(strategy_class)

        #Add Built in Classes
        self.add_strategy(PnlTradingStrategy)
        self.add_strategy(McapTargetStrategy)
        
        #TODO throw in the rest of the baked in ones as we develop them

    def add_strategy(self, strategy_class: AbstractTradingStrategy):
        if strategy_class.name not in self.custom_strategies:
            self.custom_strategies[strategy_class.__name__] = strategy_class

    def create_strategy(self, trades_manager: AbstractTradesManager, settings: dict[str, any])->AbstractTradingStrategy:      
        strategy_name = settings.get("strategy_name", "None")
        strategy = self.custom_strategies.get(strategy_name)

        if strategy:
            return strategy.create(trades_manager, settings)
        
        
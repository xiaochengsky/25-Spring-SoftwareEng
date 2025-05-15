from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Data.TradingDTOs import *

#TODO remove inactive strategies
class StrategyRunner:
    strategy_prefix = "_strategy_"
    def __init__(self):
        self.strategy_count = 0
        self.active_strategies : dict[str, AbstractTradingStrategy] = {}

    def execute(self, strategy: AbstractTradingStrategy)->list[str]:       
        strategy.start()
        strategy_id = self.strategy_prefix + str(self.strategy_count)

        self.active_strategies[strategy_id] = strategy

        self.strategy_count += 1 

        return [strategy_id]
    
    def delete_strategy(self, strategy_id: str):
        if strategy_id in self.active_strategies:
            self.active_strategies.pop(strategy_id)
    
    def get_strategy(self, strategy_id: str)->AbstractTradingStrategy:
        return self.active_strategies.get(strategy_id)

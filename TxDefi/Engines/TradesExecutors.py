from abc import abstractmethod
from TxDefi.Abstractions.OrderExecutor import OrderExecutor
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Strategies.StrategyRunner import StrategyRunner
from TxDefi.Strategies.McapTargetStrategy import McapTargetStrategy
from TxDefi.Strategies.PnlTradingStrategy import PnlTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Data.TradingDTOs import *

T = TypeVar("T", bound=ExecutableOrder)  # Generic type Key Pair Type

class GenericExecutor(OrderExecutor[T]):
    def __init__(self, trades_manager: AbstractTradesManager, strategy_executor: StrategyRunner):
        OrderExecutor.__init__(self)
        self.trades_manager = trades_manager
        self.strategy_executor = strategy_executor

    @abstractmethod
    def create_strategy(self)->AbstractTradingStrategy:
        pass

    def execute_impl(self, order: T, max_tries: int)->list[str]:        
            strategy = self.create_strategy()

            strategy.load_from_obj(order)

            for _ in range(max_tries):
                ret_val = self.strategy_executor.execute(strategy)

                if ret_val:
                    return ret_val   

class PnlExecutor(GenericExecutor[OrderWithLimitsStops]):
    def __init__(self, trades_manager: AbstractTradesManager, strategy_executor: StrategyRunner):
        GenericExecutor.__init__(self, trades_manager, strategy_executor)

    def create_strategy(self)->AbstractTradingStrategy:
        return PnlTradingStrategy(self.trades_manager)
    
class McapExecutor(GenericExecutor[McapOrder]):
    def __init__(self, trades_manager: AbstractTradesManager, strategy_executor: StrategyRunner):
        GenericExecutor.__init__(self, trades_manager, strategy_executor)

    def create_strategy(self)->AbstractTradingStrategy:
        return McapTargetStrategy(self.trades_manager)
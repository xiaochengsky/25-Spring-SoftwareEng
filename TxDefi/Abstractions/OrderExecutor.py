import threading
import time
from abc import abstractmethod
from typing import TypeVar, Generic
from TxDefi.Data.TradingDTOs import *
from TxDefi.Utilities.RateLimiter import RateLimiter

T = TypeVar("T", bound=ExecutableOrder)  # Generic type for Order subclasses

class OrderExecutor(Generic[T]):
    def __init__(self, rate_limit: float = None):
        self.rate_limiter: RateLimiter = None
        self.cancel_event = threading.Event()
        self.sems_acquired = 0

        if rate_limit:
            self.rate_limiter = RateLimiter(rate_limit)
            self.rate_limiter.start()

    def execute(self, order: T, max_tries: int)->list[str]:
        if self.rate_limiter:
            self.rate_limiter.acquire_sem()

        return self.execute_impl(order, max_tries)

    def stop(self):
        if self.rate_limiter:
            self.rate_limiter.stop()
        self.cancel_event.set()
        
    @abstractmethod
    def execute_impl(self, order: T, max_tries: int)->list[str]:
        pass
      
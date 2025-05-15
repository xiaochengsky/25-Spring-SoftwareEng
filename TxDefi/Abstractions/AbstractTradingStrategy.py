from abc import abstractmethod
from pubsub import pub
from abc import ABC
import queue
import threading
import concurrent.futures
from typing import TypeVar, Generic
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Abstractions.AbstractSubscriber import AbstractSubscriber
from TxDefi.Data.MarketEnums import *

T = TypeVar("T", bound=object)  # Generic type Key Pair Type
class AbstractTradingStrategy(ABC, threading.Thread, Generic[T], AbstractSubscriber[T]):
    def __init__(self, trades_manager: AbstractTradesManager, subbed_topics: list[str] = [], settings: dict[str, any] = None):
        threading.Thread.__init__(self, daemon=True)
        AbstractSubscriber.__init__(self)
        self.name = AbstractTradingStrategy.__name__
        self.trades_manager = trades_manager        
        self.state = StrategyState.PENDING
        self.unprocessed_event_counter = 0
        self.subbed_topics : list[str] = subbed_topics
        self.updates_lock = threading.Lock()
        self.event_queue = queue.Queue()
        self.event_count = 0
        
        if settings:
            self.load_from_dict(settings)
        
    def run(self):
        for subbed_topic in self.subbed_topics:
            pub.subscribe(topicName=subbed_topic, listener=self._handle_update)

    def stop(self):
        for subbed_topic in self.subbed_topics:
            pub.unsubscribe(topicName=subbed_topic, listener=self._handle_update)

    def _process_event_task(self, event: T):
        with self.updates_lock:
            event_count = self.event_count
            self.event_count += 1
            
        self.process_event(event_count, event)     

    def set_strategy_complete(self):
        self.state = StrategyState.COMPLETE

    def update(self, arg1: T):
        if self.state != StrategyState.COMPLETE:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                executor.submit(self._process_event_task, (arg1))
        else:
            self.stop()
                        
    def _handle_update(self, arg1: T):
        self.update(arg1)
    
    @abstractmethod
    def load_from_dict(self, strategy_settings: dict[str, any]): 
        pass

    @abstractmethod
    def load_from_obj(self, obj: object): 
        pass

    @abstractmethod
    def process_event(self, id: int, event: any):
        pass
    
    @classmethod
    @abstractmethod
    def create(self, trades_manager: AbstractTradesManager, settings: dict[str, any])->"AbstractTradingStrategy":
        pass
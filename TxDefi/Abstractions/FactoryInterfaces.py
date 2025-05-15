from abc import abstractmethod
import threading

class ThreadWorkerFactory:  
    @abstractmethod  
    def create(self, strategy_settings: dict[str, any])->threading.Thread:
        pass
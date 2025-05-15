from queue import Queue
from typing import TypeVar, Generic
from abc import abstractmethod
import concurrent.futures
import threading

T = TypeVar("T", bound=object)  # Generic type Key Pair Type
class AbstractQueueProcessor(threading.Thread, Generic[T]):
    def __init__(self):
        threading.Thread.__init__(self, daemon=True)
        self.name = AbstractQueueProcessor.__name__
        self.cancel_token = threading.Event()
        self.message_queue = Queue()

    def _process_messages(self):
        try:
            while not self.cancel_token.is_set():
                message = self.message_queue.get()
                self.process_message(message)
        except Exception as e:
            print("Error in AbstractQueueProcessor" + str(e))
        print("AbstractQueueProcessor stopped")

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.submit(self._process_messages)
            executor.submit(self.init_processor)
    
    def stop(self):
        self.cancel_token.set()
        self.message_queue.put(None)

    @abstractmethod
    def init_processor(self):
        pass

    @abstractmethod
    def process_message(self, message: T):
        pass
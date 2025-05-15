from abc import abstractmethod
from typing import TypeVar, Generic
import threading

T_Data = TypeVar("T", bound=object)  # Generic type Key Pair Type
class AbstractSubscriber(Generic[T_Data]):
    next_id = 0
    id_lock = threading.Lock()

    def __init__(self):
        with self.id_lock:    
            self.id = AbstractSubscriber.next_id
            self.subription_keys: set[str] = set()
            AbstractSubscriber.next_id += 1

    def get_id(self):
        return self.id
    
    def has_key(self, key: str)->set:
        return key in self.subription_keys
    
    def remove_key(self, key: str)->set:
        if key in self.subription_keys:
            self.subription_keys.remove(key)
    
    @abstractmethod
    def update(self, data: T_Data):
        pass
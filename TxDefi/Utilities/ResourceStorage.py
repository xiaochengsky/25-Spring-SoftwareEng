from typing import TypeVar, Generic

T = TypeVar("T", bound=object)  # Generic type Key Pair Type

class ResourceStorage(Generic[T]):
    def __init__(self, limit: int, purge_amount: int):
        self.limit = limit
        self.purge_amount = purge_amount #purge amount at limit
        self.resources : dict[str, T] = {}

    def add_resource(self, token_address, resource: T):
        if token_address not in self.resources:
            self.resources[token_address] = resource

        if len(self.resources) > 2000: #Cleanup Task so memory usage doesn't get to large
            self.saved_transactions = dict(list(self.resources.items())[self.purge_amount:])

    def get_resource(self, resource_id: str):
        return self.resources.get(resource_id)
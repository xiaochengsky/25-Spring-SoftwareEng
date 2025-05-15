from abc import abstractmethod
from typing import TypeVar, Generic
from TxDefi.Data.TradingDTOs import *
T_Transaction_Type = TypeVar("T_Transaction_Type", bound=object)  # Generic type for Order subclasses
T_Order_Type = TypeVar("T_Order_Type", bound=ExecutableOrder)  # Generic type for Order subclasses
T_Signer_Type = TypeVar("T_Signer_Type", bound=AbstractKeyPair)  # Generic type for Order subclasses

class TransactionBuilder(Generic[T_Transaction_Type]):    
    @abstractmethod
    def build_transaction(self, order: T_Order_Type, signer: T_Signer_Type)->T_Transaction_Type:
        pass
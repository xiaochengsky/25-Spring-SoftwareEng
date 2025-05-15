from abc import abstractmethod
from typing import TypeVar, Generic
import TxDefi.Utilities.Encryption as encryption_util
from TxDefi.Utilities.Encryption import SupportEncryption
from TxDefi.Data.Amount import Amount

T = TypeVar("T", bound=object)  # Generic type Key Pair Type

class AbstractKeyPair(Generic[T]):
    def __init__(self, key: str | bytes, encryption: SupportEncryption, is_encrypted: bool, amount_in: Amount):
        self.is_encrypted = is_encrypted

        if is_encrypted:
            self.encrypted_key = key
            self.decrypted_key = None
        else:
           self.encrypted_key = None
           self.decrypted_key = key    
            
        self.encryption = encryption
        self.amount_in = amount_in

    def set_amount_in(self, amount_in: Amount):
        self.amount_in = amount_in
        
    def encrypt(self)->str | bytes:
        if not self.is_encrypted:
            self.encrypted_key = encryption_util.encrypt(self.decrypted_key, self.encryption)
            self.decrypted_key = None #Remove the decrypted key from memory
            self.is_encrypted = True
        
        return self.encrypted_key

    def decrypt(self)->str | bytes:
        if self.is_encrypted:
            self.decrypted_key = encryption_util.decrypt(self.encrypted_key, self.encryption)
            self.is_encrypted = False

        return self.decrypted_key

    #Generate a usable keypair to sign transactions
    @abstractmethod
    def get_key_pair(self)->T:
        pass
   
    @abstractmethod
    def get_account_address(self)->str:
        pass
        
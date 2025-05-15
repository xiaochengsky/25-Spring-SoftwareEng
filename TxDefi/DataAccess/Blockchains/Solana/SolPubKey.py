from abc import abstractmethod
from solders.keypair import Keypair
from TxDefi.Abstractions.AbstractKeyPair import AbstractKeyPair
from TxDefi.Utilities.Encryption import SupportEncryption
from TxDefi.Data.Amount import Amount

class SolPubKey(AbstractKeyPair[Keypair]):
    def __init__(self, key: str | bytes, encryption: SupportEncryption, is_encrypted: bool, amount_in: Amount):
        AbstractKeyPair.__init__(self, key, encryption, is_encrypted, amount_in)
        self.account_keypair = None
        
        self.decrypt() #TODO Prompt user for authentication, will remain decrypted through the session of the app
       
    def encrypt(self):
        ret_val = super().encrypt()
        self.account_keypair = None

        return ret_val
    
    def decrypt(self):
        ret_val = super().decrypt()
        self.account_keypair = Keypair.from_base58_string(self.decrypted_key)

        return ret_val
    
    #Generate a usable Pubkey to sign transactions
    def get_key_pair(self)->Keypair:
        return self.account_keypair
   
    def get_account_address(self)->str:
        if self.account_keypair:
            return str(self.account_keypair.pubkey())

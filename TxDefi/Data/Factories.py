from abc import abstractmethod
from TxDefi.Abstractions.AbstractKeyPair import AbstractKeyPair
from TxDefi.Utilities.Encryption import SupportEncryption
from TxDefi.Data.MarketEnums import Blockchain
from TxDefi.Data.WebMessage import WebMessage
from TxDefi.DataAccess.Blockchains.Solana.SolPubKey import SolPubKey

class WebMessageFactory:
    @staticmethod
    def create_web_message(data):
        if isinstance(data, dict):
            user = data.get('title')
            message = data.get('message')

            if user and message and len(message) > 0:
                web_message = WebMessage()
                web_message.user = user
                web_message.message = message
                web_message.timestamp = data.get('timestamp')
                web_message.appname = data.get('appname')

                return web_message
            
        return None

class KeyPairFactory:
    def create(key: str, chain: Blockchain, encryption: SupportEncryption, is_encrypted: bool, custom_amount_in: float)->AbstractKeyPair:
        if chain == Blockchain.SOL:       
            return SolPubKey(key, encryption, is_encrypted, custom_amount_in)
           
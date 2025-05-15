from TxDefi.DataAccess.Decoders.MessageDecoder import MessageDecoder
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi

class AccountNotification:
    def __init__(self, subscription_id: int, slot: int, contract_address: str, lamports: int, account_data: list[str] | dict):
        self.subscription_id = subscription_id
        self.contract_address = contract_address #replaces tx_signature as getting this is expensive; can retrieve this from the rpc later
        self.slot = slot
        self.lamports = lamports
        self.account_data = account_data

class AccountNotificationDecoder(MessageDecoder[AccountNotification]):
    def __init__(self, contract_address: str, solana_api: SolanaRpcApi):
        self.contract_address = contract_address
        self.solana_api = solana_api

    def decode(self, data: dict)->AccountNotification:
        try:            
            slot = data['params']['result']['context']['slot']
            value = data['params']['result']['value']
            subscription_id = data['params']['subscription']
            lamports = value['lamports']
            account_data = value['data']
            self.contract_address = self.contract_address 

            return AccountNotification(subscription_id, slot, self.contract_address, lamports, account_data)
        except Exception as e:
            print("AccountInfoDecoder: Error parsing data")
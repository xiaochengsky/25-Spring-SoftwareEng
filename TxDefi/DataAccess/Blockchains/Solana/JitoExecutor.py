import base58
import time
from jsonrpcclient import request
import threading
from concurrent.futures import ThreadPoolExecutor
from solders.transaction import VersionedTransaction
from SolanaTxBuilder import SolanaTxBuilder
from SolanaTradeExecutor import SolanaTradeExecutor
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import *
from TxDefi.Data.TradingDTOs import *
import TxDefi.Utilities.HttpUtils as http_utils 

def slice_array(arr, chunk_size):
    return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]

class JitoOrderExecutor(SolanaTradeExecutor):
    jito_tip_address = "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT"#os.getenv('JITO_TIP_ADDRESS') FIXME
    jito_url = "https://slc.mainnet.block-engine.jito.wtf/api/v1/bundles"#os.getenv('jito_url') FIX
    rate_limit = 5 #only 5 per second allowed
   
    def __init__(self, market_manager: AbstractMarketManager, solana_rpc_api: SolanaRpcApi, supported_builders: dict[SupportedPrograms, SolanaTxBuilder]):
        SolanaTradeExecutor.__init__(self, market_manager, solana_rpc_api, supported_builders, self.rate_limit)
        self.builders = supported_builders

    def build_transaction(self, tx_builder: SolanaTxBuilder, order: SwapOrder, signer_index: int)->VersionedTransaction:
        #Configure Jito Tip if set; Every first tx needs a jito tip
        if signer_index > 0:
            order.swap_settings.jito_tip = None
        
        return super().build_transaction(tx_builder, order, signer_index)

    def execute_list(self, transactions: list[VersionedTransaction], executor: ThreadPoolExecutor, confirm)->list[str]:
        bundles = slice_array(transactions, self.bundle_limit)
        futures = []
       
        for bundle in bundles:
            for _ in range(3): #Blast the node
                futures.append(executor.submit(self.send_jito_bundle, bundle))

        responses = [future.result() for future in futures]
        signatures = []

        for response in responses:
            if response:
                signatures.append(response.result)
                break

        self.check_jito_transaction(signatures)

        return signatures

    def send_transaction(self, transaction: VersionedTransaction, max_tries: int):
        self.solana_rpc_api.send_transaction(transaction, max_tries)

    def check_jito_transaction(self, bundle_ids: list[str]):
        #while not self.cancelToken.is_set():
        tries = 0
        while tries < 3:
            response = http_utils.post_request(self.jito_url, request(method="getBundleStatuses", id=1, params=([bundle_ids])))
            tries += 1
            if response:
                print(f"Received a transaction response: {response}")  
                tries = 3
            else:
                print(f"Failed to submit bundle:")
                time.sleep(5)

    @staticmethod
    def is_last_tx(tx_index: int, count: int):
        return True if (tx_index+1) == count or (tx_index+1) % SolanaTradeExecutor.bundle_limit == 0 else False
                        
    @staticmethod
    def send_jito_bundle(transactions: list[VersionedTransaction])->str:
        threading.current_thread().name = f"send_jito_bundle-{threading.get_ident()}"
        bundle = [base58.b58encode(bytes(tx)).decode('utf-8') for tx in transactions]
        
        return http_utils.post_request(JitoOrderExecutor.jito_url, request(method="sendBundle", id=1, params=([ bundle ])))
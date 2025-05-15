import time
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from SolanaRpcApi import SolanaRpcApi
from pathlib import Path 
import json
from anchorpy import Idl, Program
from anchorpy.provider import Provider, Wallet
from solana.rpc.async_api import AsyncClient
from concurrent.futures import ThreadPoolExecutor
from SolanaTxBuilder import SolanaTxBuilder
from TxDefi.DataAccess.Blockchains.Solana.TransactionChecker import TransactionChecker
from TxDefi.Abstractions.OrderExecutor import OrderExecutor
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
from TxDefi.Data.TradingDTOs import *
import TxDefi.Utilities.LoggerUtil as logger_util

class SolanaTradeExecutor(OrderExecutor[SwapOrder]):
    num_batched_swaps = 5 #Blast the rpc with this number of transactions to increase the chances of it landing
    bundle_limit = 5
    def __init__(self, market_manager: AbstractMarketManager, solana_rpc_api: SolanaRpcApi,
                  supported_builders: dict[SupportedPrograms, SolanaTxBuilder], rate_limit: float = None ):
        OrderExecutor.__init__(self, rate_limit)
        self.market_manager = market_manager
        self.solana_rpc_api = solana_rpc_api
        self.builders = supported_builders
    
    def build_transaction(self, tx_builder: SolanaTxBuilder, order: SwapOrder, signer_index: int)->VersionedTransaction:
        wallet = order.wallet_settings.signer_wallets[signer_index]

        return tx_builder.build_transaction(order, wallet)
         
    def build_transactions(self, order: SwapOrder)->list[VersionedTransaction]:
        token_info = self.market_manager.get_token_info(order.token_address)
        
        if token_info:
            signed_transactions : list[VersionedTransaction] = [] 
            tx_builder = self.builders.get(token_info.metadata.program_type)
            wallets = order.wallet_settings.signer_wallets

            for i in range(len(wallets)):
                signed_transaction = self.build_transaction(tx_builder, order, i)

                if signed_transaction:
                    signed_transactions.append(signed_transaction)

            return signed_transactions

    def execute_list(self, transactions: list[VersionedTransaction], executor: ThreadPoolExecutor, max_tries: int)->list[str]:
        futures = []
        
        for transaction in transactions:       
            futures.append(executor.submit(self.send_transaction, transaction, max_tries))

        return [future.result() for future in futures]
        
    def execute_impl(self, order: SwapOrder, max_tries = 3)->list[str]:
        signed_transactions = self.build_transactions(order)
        print("Done building tx: " + str(time.time_ns())) #DELETE THIS
        ret_signatures : list[str] = []
        did_succeed = True

        if signed_transactions:
            # Create ThreadPoolExecutor for transmiting the transactions
            executor = ThreadPoolExecutor(max_workers=5)

            results = self.execute_list(signed_transactions, executor, max_tries)
            
            if results:
                if order.swap_settings.confirm_transaction:
                    futures = []

                    for tx_signature in signed_transactions:
                        signature_str = str(tx_signature.signatures[0])                  
                        futures.append((signature_str, executor.submit(self.check_transaction, signature_str)))
                        
                    for result in futures:
                        if result[1]: #See if there's a signature ; [1] contains the Future
                            signature = result[0]
                            logger_util.logger.info(signature)
                            
                            ret_signatures.append(signature) 
                        else:
                            did_succeed = False
                            break
                        
                executor.shutdown(wait=False)

                if not did_succeed:
                    raise Exception("Transaction in this batch failed!")
                
                return ret_signatures
   
    def send_transaction(self, transaction: VersionedTransaction, max_tries: int)->bool:
        try:
            time_start = time.time_ns()   
            for i in range(max_tries):              
                self.solana_rpc_api.send_transaction(transaction, max_tries)
                logger_util.logger.info("Try #" + str(i+1))
                print("Try #" + str(i+1))

            logger_util.logger.info("Tx took " + str(time.time_ns()-time_start) + " ns")
        except Exception as e:                    
            logger_util.logger.info("Transaction failed to process: " + str(e))

    def check_transaction(self, tx_signature: str)->bool:    
        transaction_checker = TransactionChecker(self.solana_rpc_api, tx_signature, timeout=35)
        transaction_checker.start()

        #Wait for transaction checker to complete or timeout
        transaction_checker.join()

        return transaction_checker.did_succeed()
        
    @staticmethod
    def create_program_nc(idl_path: str)->Program:
        return SolanaTradeExecutor.create_program(idl_path, None, None)

    @staticmethod
    def create_program(idl_path: str, signer_wallet: Keypair, connection: AsyncClient)->Program:
        # Read the generated IDL.
        with Path(idl_path).open('r') as idl_file:       
            raw_idl = idl_file.read()
            idl = Idl.from_json(raw_idl)

            if not idl.metadata:
                return
            
            program_address = idl.metadata.get('address', "")
            program_address_pk = Pubkey.from_string(program_address)  

            if signer_wallet and connection:
                wallet = Wallet(signer_wallet)
                provider = Provider(connection, wallet)
            else:
                provider = None
                
            return Program(idl, program_address_pk, provider)

    @staticmethod
    def create_program2(idl_path: str, signer_wallet: Keypair, connection: AsyncClient)->Program:
        with Path(idl_path).open('r') as idl_file:
            raw_idl = idl_file.read()
            idl_string = json.loads(raw_idl)
            idl = Idl.from_json(json.dumps(idl_string))
            program_id = Pubkey.from_string(idl["address"])

            wallet = Wallet(signer_wallet)
            provider = Provider(connection, wallet)

            return Program(idl, program_id, provider)
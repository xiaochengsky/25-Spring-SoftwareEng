from solders.instruction import Instruction
from solders.transaction import VersionedTransaction, Transaction
from solders.message import MessageV0, Message
from solders.hash import Hash
from abc import abstractmethod
from SolanaRpcApi import SolanaRpcApi
from TxDefi.DataAccess.Blockchains.Solana.SolPubKey import SolPubKey
from TxDefi.Abstractions.TransactionBuilder import TransactionBuilder
from TxDefi.Data.TradingDTOs import *

class SolanaTxBuilder(TransactionBuilder[VersionedTransaction]):
    def __init__(self, solana_rpc_api: SolanaRpcApi):
        self.solana_rpc_api = solana_rpc_api

    def build_v0_transaction(self, instructions: list[Instruction], signer: SolPubKey)->VersionedTransaction:        
        signer_pubkey = signer.get_key_pair().pubkey()
        blockhash = self.solana_rpc_api.get_last_recorded_block_hash()
        message = Message(instructions, signer_pubkey)
        
        return Transaction([signer.get_key_pair()], message, blockhash)
        #messageV0 = MessageV0.try_compile(signer_pubkey, instructions, [], self.solana_rpc_api.get_last_recorded_block_hash())
        #return VersionedTransaction(messageV0, [signer.get_key_pair()])
       
    @abstractmethod
    def build_transaction(self, order: SwapOrder, signer: SolPubKey)->VersionedTransaction:
        pass
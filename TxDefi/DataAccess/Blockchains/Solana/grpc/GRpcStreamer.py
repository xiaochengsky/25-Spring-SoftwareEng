import grpc
from solders.pubkey import Pubkey
import base58
import threading
import json
from pubsub import pub

import os
import sys
import json

# insert root directory into python module search path
sys.path.insert(1, os.getcwd())
from TxDefi.DataAccess.Decoders.MessageDecoder import MessageDecoder
import geyser_pb2
import geyser_pb2_grpc
from TxDefi.DataAccess.Decoders.TransactionsDecoder import TransactionsDecoder
from TxDefi.DataAccess.Blockchains.Solana.grpc.solana_storage_pb2 import TokenBalance
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.Data.TransactionInfo import *
import TxDefi.Data.Globals as globals

class SerializableUiTokenAmount:
    def __init__(self, uiAmount: float, decimals: int, amount: int, uiAmountString: str):
        self.uiAmount = uiAmount
        self.decimals = decimals
        self.amount = amount
        self.uiAmountString = uiAmountString
    
    def to_json(self):
        return json.dumps(self.__dict__)  # Convert object to JSON

class SerializablePubkey:
    def __init__(self, pubkey: str, writable: bool, signer: bool, source = 'transaction'):
        self.pubkey = pubkey
        self.writable = writable
        self.signer = signer
        self.source = source
    
    def to_json(self):
        return json.dumps(self.__dict__)  # Convert object to JSON
    
class SerializableTokenBalance:
    def __init__(self, accountIndex: int, mint: str, uiTokenAmount: SerializableUiTokenAmount, owner: str, programId: str):
        self.accountIndex = accountIndex
        self.mint = mint
        self.uiTokenAmount = uiTokenAmount
        self.owner = owner
        self.programId = programId

    def to_dict(self):
        ret_dict = self.__dict__
        ret_dict['uiTokenAmount'] = self.uiTokenAmount.__dict__
        return ret_dict

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__)
    
def parse_token_balance(grpc_balance: TokenBalance)->SerializableTokenBalance:
    ui_token_amount = SerializableUiTokenAmount(grpc_balance.ui_token_amount.ui_amount, grpc_balance.ui_token_amount.decimals,
                                                 grpc_balance.ui_token_amount.amount,  grpc_balance.ui_token_amount.ui_amount_string)
    return SerializableTokenBalance(grpc_balance.account_index, grpc_balance.mint, ui_token_amount, grpc_balance.owner,
                                    grpc_balance.program_id)
   
class YellowstoneGrpcStreamReader(threading.Thread):
    address_lookup_tables : dict[str, dict] = {}

    def __init__(self, endpoint, solana_rpc: SolanaRpcApi, tx_decoder: TransactionsDecoder, program_ids: list[str]):
        threading.Thread.__init__(self)
        self.cancel_token = threading.Event()
        self.endpoint = endpoint   
        self.solana_rpc = solana_rpc
        self.tx_decoder = tx_decoder
        self.program_ids = program_ids
        self.slot = 0

    def run(self):
        # Create an insecure gRPC channel
        channel = grpc.insecure_channel(self.endpoint)

        # Create a stub (client)
        stub = geyser_pb2_grpc.GeyserStub(channel)
        #response = stub.GetSlot(geyser_pb2.GetSlotRequest())
        #print(response)

        # Define your subscription request
        request = geyser_pb2.SubscribeRequest(
            transactions={
                "amms": geyser_pb2.SubscribeRequestFilterTransactions(
                    failed = False,
                    account_include = self.program_ids
                )
            },
            commitment=geyser_pb2.CommitmentLevel.PROCESSED
        )

        # Create a subscription stream
        grpc_stream = stub.Subscribe(iter([request]))
        self._read_socket(grpc_stream)

    def parse_grpc_instruction(self, grpc_instruction, all_accounts: list[dict])->InstructionInfo:
        if len(grpc_instruction.accounts) > 0:
            program_id_index = grpc_instruction.program_id_index
            accounts : list[str] = []
            data = grpc_instruction.data

            for account_index in grpc_instruction.accounts:
                if account_index < len(all_accounts):
                    accounts.append(all_accounts[account_index].get('pubkey'))

            program_account = all_accounts[program_id_index]['pubkey']
            decoder = self.tx_decoder.get_instructions_decoder(program_account)

            if decoder:
                data_dict = {"accounts": accounts, "data": [data, MessageDecoder.no_encoding]}
                instruction_data = decoder.decode(data_dict)

                if instruction_data and isinstance(instruction_data, InstructionData):
                    return InstructionInfo(instruction_data.get_type(), accounts, instruction_data)
        
    def _read_socket(self, grpc_stream):
        while not self.cancel_token.is_set():
            # Handle incoming data
            try:
                for response in grpc_stream:
                    if response.HasField("transaction"):   
                        transaction_update: geyser_pb2.SubscribeUpdateTransaction = response.transaction
                        self.slot = transaction_update.slot

                        tx_signatures = transaction_update.transaction.transaction.signatures
                        transaction_message = transaction_update.transaction.transaction.message
                        account_keys = transaction_message.account_keys
                        address_table_lookups = transaction_message.address_table_lookups #TODO use this to init account infos correctly
                        instructions = transaction_message.instructions

                        transaction_meta : geyser_pb2.TransactionStatusMeta = transaction_update.transaction.meta
                        fee = transaction_meta.fee
                        pre_balances = list(transaction_meta.pre_balances)
                        post_balances = list(transaction_meta.post_balances)
                        log_messages = list(transaction_meta.log_messages)
                    
                        inner_instructions : geyser_pb2.InnerInstructions = transaction_meta.inner_instructions
                
                        pre_token_balances_grpc = transaction_meta.pre_token_balances
                        post_token_balances_grpc = transaction_meta.post_token_balances
                        compute_units_consumed = transaction_meta.compute_units_consumed
                
                        all_accounts : list[dict] = []
                        parsed_pre_token_balance : list[dict] = []
                        parsed_post_token_balance : list[dict] = []
             
                        for i in range(len(account_keys)):
                            pubkey = Pubkey.from_bytes(account_keys[i])               
                            spubkey = SerializablePubkey(str(pubkey), False, False)
            
                            all_accounts.append(spubkey.__dict__)

                            if i == 0:
                                payer_address = spubkey.pubkey
                                spubkey.signer = True

                        for account in address_table_lookups:
                            table_lookup_address =  base58.b58encode(account.account_key).decode('utf-8')

                            account_info = self.address_lookup_tables.get(table_lookup_address)

                            if not account_info:
                                account_info = self.solana_rpc.get_account_info(table_lookup_address)
                                
                                if account_info:
                                    self.address_lookup_tables[table_lookup_address] = account_info #Save for later

                            if account_info:
                                addresses = account_info.get('value', {}).get('data', {}).get('parsed', {}).get('info', {}).get('addresses')
                                 
                                for address in addresses:
                                    spubkey = SerializablePubkey(str(address), False, False)
                                    all_accounts.append(spubkey.__dict__)
                                        
                        for token_balance in pre_token_balances_grpc:
                            parsed_token_balance = parse_token_balance(token_balance)
                            parsed_pre_token_balance.append(parsed_token_balance.to_dict())

                        for token_balance in post_token_balances_grpc:
                            parsed_token_balance = parse_token_balance(token_balance)
                            parsed_post_token_balance.append(parsed_token_balance.to_dict())
                        
                        all_instructions : list[InstructionInfo] = []
                        
                        for instruction in instructions:
                            instruction_info = self.parse_grpc_instruction(instruction, all_accounts)

                            if instruction_info:
                                all_instructions.append(instruction_info)

                        #for instructionl1 in inner_instructions:
                        #    for instructionl2 in instructionl1.instructions:
                        #        instruction_info = self.parse_grpc_instruction(instructionl2, all_accounts)

                        #        if instruction_info:
                        #            all_instructions.append(instruction_info)

                        tx_signature = base58.b58encode(tx_signatures[0]).decode('utf-8')
                        transaction = ParsedTransaction(tx_signature, self.slot, payer_address, all_accounts, pre_balances, post_balances, parsed_pre_token_balance, 
                                        parsed_post_token_balance, fee, all_instructions, log_messages)
                        
                        pub.sendMessage(topicName=globals.topic_incoming_transactions, arg1=transaction)
                    #else:
                    #    print("Received update:", response)
            except grpc.RpcError as e:
                print(f"RPC error occurred: {e}")
    
    def stop(self):
        self.cancel_token.set()
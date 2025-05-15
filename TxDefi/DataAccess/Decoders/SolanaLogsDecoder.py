import re
from TransactionsDecoder import TransactionsDecoder
from MessageDecoder import LogsDecoder
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *

def does_match(in_string: str, regx: str):
    return bool(re.search(regx, in_string))

#Logs hierarchical container
class ProgramLogsGroup:
    invoke_regx = r'invoke \[\d+\]$'
    pg_success_regx = r"^Program .* success$"   

    def __init__(self, group_name: str, start_index: int):
        self.group_name = group_name
        self.start_index = start_index
        self.end_index = start_index
        self.should_ignore = False
        self.logs : list[str] = []
        self.inner_groups : list[ProgramLogsGroup] = []

    @staticmethod
    def match_word_in_target(strings: list[str], target: str):
        for word in strings:
            if word in target:
                return word
    
    @staticmethod
    def print_logs(logs_group: "ProgramLogsGroup"):
        print(logs_group.group_name)
        
        for log in logs_group.logs:
            print(log)

        for group in logs_group.inner_groups:
            ProgramLogsGroup.print_logs(group)

    @staticmethod
    def build_program_log_set(logs_group: "ProgramLogsGroup", logs: list[str], log_index: int)->"ProgramLogsGroup":
        if not logs_group:
            logs_group = ProgramLogsGroup("root", log_index)

        if log_index >= len(logs) :
            return logs_group

        log = logs[log_index]

        if does_match(log, ProgramLogsGroup.pg_success_regx):
            logs_group.logs.append(log)
            logs_group.end_index = log_index     
            
            return logs_group 
        elif(does_match(log, ProgramLogsGroup.invoke_regx)):
            new_logs_group = ProgramLogsGroup.build_program_log_set(ProgramLogsGroup(log, log_index), logs, log_index+1)

            if new_logs_group:
                logs_group.inner_groups.append(new_logs_group)
                log_index = new_logs_group.end_index
        else:
            logs_group.logs.append(log)

        return ProgramLogsGroup.build_program_log_set(logs_group, logs, log_index+1)
    
class SolanaLogsDecoder(LogsDecoder):
    def __init__(self, program_id: str, solana_api: SolanaRpcApi, logs_decoder: LogsDecoder, transactions_decoder: TransactionsDecoder, get_transaction = False):
        self.program_id = program_id
        self.solana_api = solana_api
        self.logs_decoder = logs_decoder
        self.transactions_decoder = transactions_decoder
        self.get_transaction = get_transaction #Retrieves and parses entire transaction if warranted  
        self.program_log_prefix = f"Program {program_id }"                
        self.program_invoke_prefix = f"{self.program_log_prefix} invoke"
        self.program_success_prefix = f"{self.program_log_prefix} success"
        self.program_failed_prefix = f"{self.program_log_prefix} failed"
        self.log_data_prefix_tuple = tuple(self.get_log_data_prefixes())

    def decode_log(self, log: str)->InstructionData:
        return self.logs_decoder.decode_log(log)
    
    def decode(self, data: dict)->list:
        if 'method' in data and data['method'] == "logsNotification":
            slot = data['params']['result']['context']['slot']
            logs = data['params']['result']['value']['logs']
            count = len(logs)
          
            if count > 0:
                signature = data['params']['result']['value']['signature']
                return self.decode_logs(logs, slot, signature)

    #Extracts all logs that begin with prefix
    def decode_logs_throw(self, logs: list[str], slot: int, signature: str)->list[InstructionData]:
        count = len(logs)

        if count > 0:
            #Filter out unsuccessful transaction
            matching_logs = [log for log in logs if log.startswith(self.log_data_prefix_tuple)]
            
            if matching_logs:
                return self.parse_logs(slot, signature, matching_logs)


    def decode_logs(self, logs: list[str], slot: int, signature: str)->list:
        count = len(logs)

        if count > 1:
            root_pl_set = ProgramLogsGroup.build_program_log_set(None, logs, 0)

            decoded_data = self.parse_program_logs_set(slot, signature, root_pl_set)
            
            if decoded_data and len(decoded_data) > 0:                
                return decoded_data
                
    def parse_program_logs_set(self, slot: int, signature: str, program_logs_set: ProgramLogsGroup)->list[InstructionData]:
        if program_logs_set.group_name.startswith(self.program_invoke_prefix):
            ret_data = self.parse_logs(slot, signature, program_logs_set.logs)
        else:
            ret_data = []
            
        for inner_set in program_logs_set.inner_groups:
            inner_ret_data = self.parse_program_logs_set(slot, signature, inner_set)

            if inner_ret_data:
                ret_data.extend(inner_ret_data)

        return ret_data

    def get_log_data_prefixes(self):
        return self.logs_decoder.get_log_data_prefixes()
   
    def parse_logs(self, slot: int, signature: str, logs: list[str])->list[InstructionData]:
        ret_decoded_messages : list[InstructionData]  = []
        matching_logs = [log for log in logs if log.startswith(self.log_data_prefix_tuple)]
        for log in matching_logs:    
            #Check for Add Liquidity, Remove Liquidity, and Burn Verbage
            #if any(word in log for word in self.get_log_data_prefixes()): #DELETE
            decoded_data = self.decode_log(log)
            
            if decoded_data:
                decoded_data.slot = slot
                decoded_data.tx_signature = signature
                
                if isinstance(decoded_data, ExtendedMetadata) or isinstance(decoded_data, RetailTransaction):                        
                    ret_decoded_messages.append(decoded_data)
                elif isinstance(decoded_data, LiquidityPoolData) or isinstance(decoded_data, SwapData) or isinstance(decoded_data, PumpMigration):
                    if self.get_transaction:
                        #Not enough data in these logs, so need to retrieve the entire transaction #Expensive operation
                        transaction = self.solana_api.get_transaction(signature)
                        transaction_data = self.transactions_decoder.decode(transaction)

                        if transaction_data:
                            ret_decoded_messages.append(transaction_data)
                    else:                         
                        ret_decoded_messages.append(decoded_data)

        return ret_decoded_messages
        #DELETE Pump was giving before and after shots, but is not doing that anymore 1/28
        #if len(trade_messages) == 1:
        #    ret_decoded_messages.extend(trade_messages)
        #elif len(trade_messages) > 1:
        #    for indx in range(len(trade_messages)):
        #        if (indx+1) % 2 == 0: #Only add even messages Pump puts out 2, 1 for before and 1 for after transaction succeeds #TODO Reevaluate if this is needed
        #            ret_decoded_messages.append(trade_messages[indx])


logs = [
        'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [2]',
        'Program log: Instruction: Buy',
        'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [3]',
        'Program log: Instruction: Transfer',
        'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4645 of 575560 compute units',
        'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success',
        'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [3]',
        'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P consumed 2132 of 567249 compute units',
        'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success',
        'Program data: vdt/007mYe6xaRNpCCRfbnje3xwup1ffNo/9DAXtjjW4mbQcEISUXxujOAEAAAAA1YrUgaoAAAAAA/L5gwYEaOE0R9zSh5tV/SDp6aZQRCwW+GAUjtWqYto08ZpnAAAAAAisI/wGAAAA+pvWR+PPAwAIAAAAAAAAAPoDxPtR0QIA',
        'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success'
        ]
#pl_group = ProgramLogsGroup.build_program_log_set(None, logs, 0)
#ProgramLogsGroup.print_logs(pl_group)
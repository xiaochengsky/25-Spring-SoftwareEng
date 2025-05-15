from datetime import datetime
from MessageDecoder import MessageDecoder
from TxDefi.Data.TransactionInfo import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
    
class TransactionsDecoder(MessageDecoder[ParsedTransaction]):
    main_instructions_keys = ['transaction', 'message', 'instructions']
    inner_instructions_keys = ['meta', 'innerInstructions']
    log_messages_keys = ['meta', 'logMessages']
    err_message_keys = ['meta', 'err']
    transfer_type = 'transfer'
    transaction_notification = 'transactionNotification'

    def __init__(self):
        self.supported_decoders : dict[str, MessageDecoder[dict]] = {}

    def decode(self, data: dict)->ParsedTransaction:
        if data.get('method', '') == TransactionsDecoder.transaction_notification:
            transaction_data = data.get('params', {}).get('result', {}).get('transaction', {})
            slot = data.get('params', {}).get('result', {}).get('slot')
        else:
            transaction_data = data
            slot = data.get('slot')
 
        error_messages = TransactionsDecoder.get_value(transaction_data, TransactionsDecoder.err_message_keys)
        
        #Only process if this is a passing transaction
        if not error_messages and not transaction_data.get('error') and slot:
            return self.process_transaction(transaction_data, slot)

    def process_transaction(self, data: dict, slot: int)->ParsedTransaction:      
        all_accounts = data['transaction']['message']['accountKeys']
        fees = data['meta']['fee']
        log_messages = data['meta']['logMessages']
        pre_sol_balances = data['meta']['preBalances']
        post_sol_balances = data['meta']['postBalances']
        pre_token_balances = data['meta']['preTokenBalances']
        post_token_balances = data['meta']['postTokenBalances']
        tx_signature = data['transaction']['signatures'][0]
        payer_address = all_accounts[0]['pubkey']   
        instructions = TransactionsDecoder.get_value(data, TransactionsDecoder.main_instructions_keys)
        
        instruction_list = self.parse_instructions(instructions, tx_signature)
        inner_instructions = TransactionsDecoder.get_inner_instructions(data)
       
        if inner_instructions and len(inner_instructions) > 0:
            inner_instruction_list = self.parse_instructions(inner_instructions, tx_signature)

            if instruction_list:
                instruction_list.extend(inner_instruction_list)
            else:
                instruction_list = inner_instruction_list

        if instruction_list:
            return ParsedTransaction(tx_signature, slot, payer_address, all_accounts, pre_sol_balances, post_sol_balances, pre_token_balances, 
                                     post_token_balances, fees, instruction_list, log_messages)
                
    def parse_instructions(self, instructions: dict, tx_signature: str)->list[InstructionInfo]:
        instruction_infos : list[InstructionInfo] = []

        if instructions:
            for instruction in instructions:
                try:
                    #Figure out what type of transaction this is
                    parsed_instruction = self.get_instruction_info(instruction)

                    if parsed_instruction:
                        parsed_instruction.data.tx_signature = tx_signature
                        instruction_infos.append(parsed_instruction)
                except Exception as e:
                    print("Problem parsing " + str(instruction))
                    pass
                    #self.parse_instructions(instructions) #Leave for debugging
        if len(instruction_infos):
            return instruction_infos
        else:
            pass
    
    def is_supported_amm(self, program_address: str):
        return program_address in self.supported_decoders
    
    def parse_account_data(self, account_info: dict)->InstructionData:
        value = account_info.get("value",{})
        owner = account_info.get("value",{}).get("owner")

        if owner and owner in self.supported_decoders.keys():                
            return self.supported_decoders[owner].decode(value)
        
    def add_data_decoder(self, program_id: str, decoder: MessageDecoder):
        self.supported_decoders[program_id] = decoder
    
    def get_instructions_decoder(self, program_id: str):
        if program_id in self.supported_decoders:
            return self.supported_decoders[program_id]

    def get_instruction_info(self, instruction_dict: dict)->InstructionInfo:
        program_id = instruction_dict.get('programId', None)
        parsed_data = instruction_dict.get('parsed', None)
        instruction_accounts = instruction_dict.get('accounts', {})

        if program_id and program_id in self.supported_decoders and len(instruction_accounts) >= 2: #Program Transaction                 
            decoded_data = self.supported_decoders[program_id].decode(instruction_dict)
    
            if decoded_data:
                return InstructionInfo(decoded_data.get_type(), instruction_accounts, decoded_data)
        elif parsed_data and isinstance(parsed_data, dict) and parsed_data.get('type'): 
            info_type = TradeEventType.to_enum(parsed_data['type'])
            instruction_dict = parsed_data['info']

            if info_type == TradeEventType.SOL_TRANSFER:
                source = instruction_dict['source']
                destination = instruction_dict['destination']
                lamports = instruction_dict.get('lamports', 0)

                transfer_data = TransferData(source, destination, lamports)
            
                return InstructionInfo(info_type, instruction_accounts, transfer_data)
            elif info_type == TradeEventType.TOKEN_TRANSFER:
                source = instruction_dict['source']
                destination = instruction_dict['destination']
                mint = instruction_dict['mint']
              
                authority = instruction_dict.get('authority', None)

                if not authority:
                    authority = instruction_dict.get('multisigAuthority', '')

                signers = instruction_dict.get('signers', '')
                token_amount = TransactionsDecoder.get_token_amount(instruction_dict['tokenAmount'])

                transfer_data = TransferCheckedData_json(source, destination, mint, authority, signers, token_amount)

                return InstructionInfo(info_type, instruction_accounts, transfer_data)
   
    #TODO optimization, check instructions on transaction instead of parsing the logs
    @staticmethod
    def check_added_liquidity(logs: list[str]): #REDO this is slow
        for line in logs:
            if 'InitializeMint2' in line:
                return True
        
        return False
    
    @staticmethod
    def check_removed_liquidity(logs: list[str]): #REDO this is slow
        for line in logs:
            if 'Program log: Instruction: Withdraw' in line:
                return True
        
        return False
    
    @staticmethod
    def check_burned(logs: list[str]): #REDO this is slow
        for line in logs:
            if 'Program log: Instruction: Burn' in line:
                return True
        
        return False
    
    #DELETE
    @staticmethod 
    def get_pool_info(account_address: str, all_accounts: dict[str], token_balances: dict):
        for token_balance in token_balances:        
            account_index = token_balance['accountIndex']

            if account_index < len(all_accounts) and account_address == all_accounts[account_index]['pubkey']:
                return token_balance

    @staticmethod
    def extract_balance_info(owner_address: str, token_balances: list[dict])->dict[str, TokenAccount_json]:
        ret_balances : dict[int, TokenAccount_json] = {}

        for token_balance in token_balances:
            token_owner_address = token_balance['owner']

            if token_owner_address == owner_address:   
                mint_address = token_balance['mint']          
                token_ui_balance = token_balance['uiTokenAmount']["uiAmount"]

                if mint_address not in ret_balances:
                    account_index = token_balance['accountIndex']
                    ret_balances[mint_address] = TokenAccount_json(account_index, owner_address, mint_address)
                            
                ret_balances[mint_address].ui_balance += token_ui_balance
            
        return ret_balances

    @staticmethod
    def get_token_amount(token_amount: dict)->TokenAmount_json:
        amount = token_amount['amount']
        decimals = token_amount['decimals']
        ui_amount = token_amount['uiAmount']
        ui_amount_string = token_amount['uiAmountString']

        return TokenAmount_json(amount, decimals, ui_amount, ui_amount_string)
  
    @staticmethod
    def get_inner_instructions(json_parsed_transaction: dict)->list:
        ret_instructions = []
        inner_instructions = TransactionsDecoder.get_value(json_parsed_transaction, TransactionsDecoder.inner_instructions_keys)
        
        for program_instructions in inner_instructions:
            nested_instructions = program_instructions.get('instructions')

            if nested_instructions:
                ret_instructions.extend(nested_instructions)
                
        return ret_instructions

    @staticmethod
    def get_instructions_element(json_parsed_transaction: dict, program_id: str)->dict:
        #Check if it's a Standard Transaction
        instructions = TransactionsDecoder.get_value(json_parsed_transaction, TransactionsDecoder.main_instructions_keys)
      
        if len(instructions) > 0:
            instructions_element = TransactionsDecoder.get_key_value_element(instructions, 'programId', program_id)

            if instructions_element:
                return instructions_element
          
            #Check if it's Block Route Transaction
            inner_instructions = TransactionsDecoder.get_value(json_parsed_transaction, TransactionsDecoder.inner_instructions_keys)

            if len(inner_instructions) > 0:
                for program_instructions in inner_instructions:
                    nested_instructions = program_instructions.get('instructions', [])

                    instructions_element = TransactionsDecoder.get_key_value_element(nested_instructions, 'programId', program_id)

                    if instructions_element:
                        return instructions_element
                    
            else:
                print("TransactionDecoder: Unsupported transaction format")

    #Gets first matching key value pair in the list
    @staticmethod
    def get_key_value_element(alist: list, key, value):
        for element in alist:
            if element.get(key, '') == value:
                return element

    #Get the element given an ordered key list
    @staticmethod
    def get_value(keyValues: dict, keys: list):
        element = keyValues

        for key in keys:
            element = element.get(key, "fail")
            
            if element == "fail":
                return {}

        return element    

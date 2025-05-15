from construct import Adapter
import time
from anchorpy.coder.coder import Coder
from MessageDecoder import LogsDecoder
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *

class BondimgCurveData:
    def __init__(self):
        self.program_type = SupportedPrograms.PUMPFUN
        self.complete = False
        self.real_sol_reserves = 0
        self.real_token_reserves = 0
        self.token_total_supply = 0
        self.virtual_sol_reserves = 0
        self.virtual_token_reserves = 0
        self.token_program_address = ""

    def get_type(self):
        return TradeEventType.DATA
    
class Event:
    def __init__(self, name: str):
        self.name = name

class PumpDataDecoder(LogsDecoder):
    total_created = 0
    log_data_prefixes = [LogsDecoder.program_data_prefix, LogsDecoder.program_instruction_prefix]
    log_migrate = "Program log: Instruction: Migrate"
    pump_migration_id_bytes = 0x9beae792ec9ea21e.to_bytes(8, byteorder='big')
    pump_amm_migration_event_bytes = 0xbde95db95c94ea94.to_bytes(8, byteorder='big')
    instruction_withdraw = "Withdraw"

    program_data_index = len(LogsDecoder.program_data_prefix)

    def __init__(self, program_address: str, coders: Coder, encoding: str):
        self.program_address = program_address
        self.coders = coders
        self.encoding = encoding
        self.last_event = None

        self.coder_list = [self.coders.instruction, self.coders.accounts, self.coders.events]
        
    def get_log_data_prefixes(self):
        return PumpDataDecoder.log_data_prefixes
    
    def decode_log(self, log: str)->InstructionData:
        if self.instruction_withdraw in log or self.log_migrate in log:
            return PumpMigration("")
        elif log.startswith(LogsDecoder.program_data_prefix):   
            program_data = log[self.program_data_index:]
            program_data = program_data.strip()

            decoded_bytes = self.get_bytes(program_data, LogsDecoder.base64_encoding)
    
            return self.decode_bytes_data(decoded_bytes, self.coders.events) #Use events decoder
    
    def _retry_decode_event(self, data: bytes, exclude_coder = None):
        ret_event = None
        for coder in self.coder_list:
            try:
                if coder != exclude_coder:
                    ret_event = coder.parse(data)
                    break 
            except Exception as e:
                pass
        
        return ret_event

    def decode_bytes_data(self, data: bytes, coder: Adapter)->InstructionData:
        ret_data = None

        try:
            event = coder.parse(data)
        except Exception as e:
            data_bytes = None
            event = None
            if len(data) >= 8:
                data_bytes = data[:8]
                if data_bytes == self.pump_migration_id_bytes or data_bytes == self.pump_amm_migration_event_bytes:
                    event = Event("withdraw")            
            
            if not event:
                #Try with all the other coders
                event = self._retry_decode_event(data, coder)

                if not event:
                    #print("PumpDataDecoder: Bad data " + data.hex())   
                    return
            
        if event:                                                                                           
            if event.name == "buy":
                ret_data = SwapData(TradeEventType.BUY, event.data.max_sol_cost, event.data.amount)
            elif event.name == "sell":
                ret_data = SwapData(TradeEventType.SELL, event.data.amount, event.data.min_sol_output)
            elif event.name == "withdraw":
                ret_data = PumpMigration("") #Don't have this token address in the logs, so will have to parse the transaction later to get this
            elif event.name == "create" or event.name == "CreateEvent":
                ret_data = ExtendedMetadata("unknown")
                ret_data.name = event.data.name
                
                ret_data.symbol = event.data.symbol
                ret_data.token_decimals = 6
                ret_data.token_program_address = solana_utilites.TOKEN_PROGRAM_ADDRESS
                ret_data.program_id = self.program_address
                
                if event.name == "create":
                    ret_data.inner_metadata_uri = event.data.uri
                else:
                    ret_data.token_address = str(event.data.mint)               
                    ret_data.sol_vault_address = str(event.data.bonding_curve) #This goes nowhere
                    ret_data.creator_address = str(event.data.user)
                    ret_data.inner_metadata_uri = event.data.uri        
            elif event.name == "BondingCurve":
                ret_data = BondimgCurveData()
                ret_data.complete = event.data.complete
                ret_data.real_sol_reserves = event.data.real_sol_reserves
                ret_data.real_token_reserves = event.data.real_token_reserves
                ret_data.token_total_supply = event.data.token_total_supply
                ret_data.virtual_sol_reserves = event.data.virtual_sol_reserves
                ret_data.virtual_token_reserves = event.data.virtual_token_reserves
                ret_data.token_program_address = solana_utilites.TOKEN_PROGRAM_ADDRESS
            elif (event.name == "TradeEvent" and (self.last_event == None or event.name != self.last_event.name or
                                                    not (event.data.mint == self.last_event.data.mint and 
                                                        event.data.virtual_token_reserves == self.last_event.data.virtual_token_reserves))):
                ret_data = RetailTransaction(str(event.data.mint))
                ret_data.is_buy = event.data.is_buy
                ret_data.trade_amt_sol = event.data.sol_amount
                ret_data.token_quantity = event.data.token_amount
                ret_data.trader_address = str(event.data.user) 
                ret_data.transaction_timestamp = event.data.timestamp
                ret_data.sol_reserves = event.data.virtual_sol_reserves
                ret_data.token_reserves = event.data.virtual_token_reserves
        
        if ret_data:
            ret_data.program_type = SupportedPrograms.PUMPFUN

        self.last_event = event
        return ret_data

    def decode(self, program_data: dict)->InstructionData:   
        instruction_data = program_data.get('data')
        encoding = self.encoding
                  
        if encoding == self.base64_encoding:
            coder = self.coders.events
        else:
            coder = self.coders.instruction

        if isinstance(instruction_data, list) and len(instruction_data) >= 2: #remove check if confident
            encoding = instruction_data[1]
            instruction_data = instruction_data[0]
            
        if instruction_data:
            decoded_bytes = self.get_bytes(instruction_data, encoding) 
        
            ret_object = self.decode_bytes_data(decoded_bytes, coder)      
            
            #Create a filled out MintMetadata object
            if ret_object and (ret_object.get_type() == TradeEventType.NEW_MINT or ret_object.get_type() == TradeEventType.BONDING_COMPLETE):
                instruction_accounts = program_data.get('accounts')

                if instruction_accounts:
                    if isinstance(ret_object, ExtendedMetadata):                                     
                        #Fill out the rest of it
                        self.total_created += 1
                        ret_object.token_address = instruction_accounts[0]

                        #Set vault accounts                 
                        ret_object.sol_vault_address = instruction_accounts[2]
                        ret_object.token_vault_address = instruction_accounts[3]
                    elif isinstance(ret_object, PumpMigration):
                        ret_object.token_address = instruction_accounts[2]
                        ret_object.market_address = instruction_accounts[9]
                        ret_object.lp_token_address = instruction_accounts[15]
                        ret_object.token_vault_address = instruction_accounts[17]
                        ret_object.sol_vault_address = instruction_accounts[18]
            
            return ret_object
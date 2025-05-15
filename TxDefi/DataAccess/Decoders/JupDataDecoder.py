import os
import sys
from construct import Adapter

from TxDefi.DataAccess.Decoders.MessageDecoder import MessageDecoder
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *

class JupDataDecoder(MessageDecoder[InstructionData]):
    def __init__(self, program_id: str, coder: Adapter, encoding: str):
        self.coder = coder        
        self.program_id = program_id
        self.encoding = encoding
    
    def decode(self, program_data: str)->InstructionData:
        instruction_accounts = program_data.get('accounts', None) #TODO Add this to the data object
        instruction_data = program_data.get('data', None)

        decoded_bytes = self.get_bytes(instruction_data, self.encoding) 

        try:

            event = self.coder.parse(decoded_bytes)                
            
            if event:
                if event.name == 'route' or event.name == 'shared_accounts_route':
                    return SwapRouteData(event.data.in_amount, event.data.quoted_out_amount, event.data.slippage_bps, event.data.platform_fee_bps)
        except Exception as e:
            pass
    
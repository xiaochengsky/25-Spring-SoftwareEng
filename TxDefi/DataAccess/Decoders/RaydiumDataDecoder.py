from solders.pubkey import Pubkey
import struct
from MessageDecoder import LogsDecoder
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *

class RaydiumDataDecoder(LogsDecoder):
    initialize2_id = 0x1
    add_lq_id = 0x3
    withdraw_lq_id = 0x4
    swap_id = 0x9
    log_type_initialize2_id = 0x0
    log_type_add_lq_id = 0x1
    log_type_withdraw_lq_id = 0x2
    log_type_swap_id = 0x3
    ray_log_prefix = "Program log: ray_log: "
    program_data_index = len(ray_log_prefix)
    log_prefixes = [ray_log_prefix]

    def __init__(self, program_address: str, encoding: str):
        self.program_address = program_address
        self.encoding = encoding

    def get_log_data_prefixes(self):
        return self.log_prefixes
    
    #TODO Future Dev to get market data info from the market account
    #Not working 
    @staticmethod
    def parse_amm_info(decoded_data: bytes)->dict:
        # Initialize an offset to parse the binary data
        offset = 0

        # Helper function to read u64 values
        def read_u64(data, offset):
            value = struct.unpack_from('<Q', data, offset)[0]  # Little-endian unsigned 64-bit integer
            return value, offset + 8

        # Helper function to read publicKey values
        def read_public_key(data, offset):
            key = Pubkey(data[offset:offset + 32])  # 32 bytes for publicKey
            return key, offset + 32

        # Parsing fields
        amm_info = {}

        # Parse all u64 fields
        u64_fields = [
            "status", "nonce", "orderNum", "depth", "coinDecimals", "pcDecimals",
            "state", "resetFlag", "minSize", "volMaxCutRatio", "amountWave",
            "coinLotSize", "pcLotSize", "minPriceMultiplier", "maxPriceMultiplier",
            "sysDecimalValue", "lpAmount", "clientOrderId"
        ]

        for field in u64_fields:
            value, offset = read_u64(decoded_data, offset)
            amm_info[field] = value

        # Parse "fees" (custom-defined type)
        # Assuming "fees" is a struct; replace this with appropriate parsing logic
        fees_length = 64  # Example length for the Fees struct; adjust as needed
        amm_info["fees"] = decoded_data[offset:offset + fees_length]
        offset += fees_length

        # Parse "outPut" (custom-defined type)
        # Assuming "outPut" is a struct; replace this with appropriate parsing logic
        out_put_length = 144  # Example length for the OutPutData struct; adjust as needed
        amm_info["outPut"] = decoded_data[offset:offset + out_put_length]
        offset += out_put_length

        # Parse publicKey fields
        public_key_fields = [
            "tokenCoin", "tokenPc", "coinMint", "pcMint", "lpMint",
            "openOrders", "market", "serumDex", "targetOrders", "withdrawQueue",
            "tokenTempLp", "ammOwner"
        ]

        for field in public_key_fields:
            value, offset = read_public_key(decoded_data, offset)
            amm_info[field] = str(value)  # Convert to string for readability

        # Parse "padding" (array of two u64 values)
        padding = []
        for _ in range(2):
            value, offset = read_u64(decoded_data, offset)
            padding.append(value)
        amm_info["padding"] = padding

        return amm_info

    def decode_log(self, log: str)->InstructionData:
        if log.startswith(self.ray_log_prefix):   
            program_data = log[self.program_data_index:]
            program_data = program_data.strip()
            
            decoded_bytes = self.get_bytes(program_data, LogsDecoder.base64_encoding)
  
            if decoded_bytes:
                return self.decode_bytes_data(decoded_bytes, True)

    def decode_bytes_data(self, data: bytes, is_log_data: bool)->InstructionData:
        ret_object : InstructionData = None
        
        # Parse the discriminator (1 byte, u8)
        discriminator = struct.unpack_from('B', data, 0)[0]  # 'B' for unsigned char (1 byte)

        if is_log_data:
            if discriminator == self.log_type_initialize2_id:
                ret_object = RaydiumDataDecoder.parse_base64_data_init2(0, data)  
            elif discriminator == self.log_type_swap_id:
                ret_object = RaydiumDataDecoder.parse_base58_data_swapv2(0, data)
            elif discriminator == self.log_type_add_lq_id: 
                ret_object = RaydiumDataDecoder.parse_base64_data_add_liquidity(0, data)
            elif discriminator == self.log_type_withdraw_lq_id: 
                ret_object = RaydiumDataDecoder.parse_base64_data_withdraw_liquidity(0, data)
        else:
            if discriminator == self.initialize2_id:
                ret_object = RaydiumDataDecoder.parse_base58_data_init2(0, data)
            elif discriminator == self.swap_id:
                ret_object = RaydiumDataDecoder.parse_base58_data_swapv2(0, data)
            elif discriminator ==  self.add_lq_id:
                ret_object = RaydiumDataDecoder.parse_base64_data_add_liquidity(0, data) #FIXME if parser doesn't work
            elif discriminator == self.withdraw_lq_id: 
                ret_object = RaydiumDataDecoder.parse_base64_data_withdraw_liquidity(0, data)

        if  ret_object: 
            ret_object.program_type = SupportedPrograms.RAYDIUMLEGACY
        
        return ret_object

    def decode(self, program_data: dict)->InstructionData:
        ret_object : InstructionData = None
        instruction_accounts = program_data.get('accounts', None)
        instruction_data = program_data.get('data', None)

        if instruction_accounts and instruction_data:      
            encoding = self.encoding

            if isinstance(instruction_data, list) and len(instruction_data) >= 2: #remove check if confident #TODO Abstract this
                encoding = instruction_data[1]
                instruction_data = instruction_data[0]    

            decoded_bytes = self.get_bytes(instruction_data, encoding)
        
            if decoded_bytes:                      
                accounts_count = len(instruction_accounts)

                ret_object = self.decode_bytes_data(decoded_bytes, False)

                if isinstance(ret_object, AmmSwapData):
                    ret_object.market_address = instruction_accounts[1] #Save for the future
                    ret_object.amm_authority_address = instruction_accounts[2] #3rd account
                    
                    if accounts_count == 17:
                        pool1_account_index = 4
                        pool2_account_index = 5
                        user_in_account_index = 14
                        user_out_account_index = 15
                    elif accounts_count == 18: 
                        pool1_account_index = 5
                        pool2_account_index = 6
                        user_in_account_index = 15
                        user_out_account_index = 16
                    else:
                        return None                
          
                    ret_object.pool_base_address = instruction_accounts[pool1_account_index] 
                    ret_object.pool_quote_address = instruction_accounts[pool2_account_index]
                    ret_object.user_in_account = instruction_accounts[user_in_account_index] 
                    ret_object.user_out_account = instruction_accounts[user_out_account_index] #To get mint address, find this account index in all accounts and extract entry in post token accounts 
                elif isinstance(ret_object, LiquidityPoolData):
                    if ret_object.get_type() == TradeEventType.NEW_MINT:
                        ret_object.amm_authority_address = instruction_accounts[5] #6th account
                    
                        #Make sure vaults are in the right order (SOL should always be pool1 for the rest of our code to work)
                        if instruction_accounts[8] == solana_utilites.WRAPPED_SOL_MINT_ADDRESS:
                            ret_object.token_address = instruction_accounts[9] #10th account
                            ret_object.base_mint_address = instruction_accounts[10] #11th account
                            ret_object.quote_mint_address = instruction_accounts[11] #12th account                
                        else:
                            ret_object.token_address = instruction_accounts[8] #9th account
                            ret_object.base_mint_address = instruction_accounts[11] #12th account
                            ret_object.quote_mint_address = instruction_accounts[10] #11th account          
                    elif ret_object.get_type() == TradeEventType.ADD_LIQUIDITY or ret_object.get_type() == TradeEventType.REMOVE_LIQUIDITY:                            
                        ret_object.amm_authority_address = instruction_accounts[2] 
                        ret_object.base_mint_address = instruction_accounts[6] #FYI SOL may not always be in pool1
                        ret_object.quote_mint_address = instruction_accounts[7]         

                # Initialize2 Example
                # https://solana.fm/tx/4Sx4bcZeb5tvcHrZeM3VJSPr27a5wpW3DsZPpTftpCVp9nM5vK9hhrdGwetUkzS8weVf1SUePUNVjFRDZ1JPs7wY
                # Swap Example
                #https://solana.fm/tx/37tDeh5b3iA9xBfuBrww2KfAvRyyuMVZGcmsiNB14eCf1Yyk25kMqYUV9odUXKkeUCYqJ73rF6Dc7JiEpnrwqp69?cluster=mainnet-alpha
                #ret_object = self.parse_amm_info(decoded_bytes)#self.raydium_client.coder.accounts.parse(decoded_bytes)  

        return ret_object

    @staticmethod
    def parse_base64_data_init2(start_index: int, decoded_bytes: bytes)->LiquidityPoolData:      
        # Parse openTime (8 bytes, u64)
        open_time = struct.unpack_from('<Q', decoded_bytes, start_index+1)[0]  # '<Q' for little-endian unsigned long long (8 bytes)
        
        # Parse initPcAmount (8 bytes, u64)
        init_pc_amount = struct.unpack_from('<Q', decoded_bytes, start_index+27)[0]
        
        # Parse initCoinAmount (8 bytes, u64)
        init_coin_amount = struct.unpack_from('<Q', decoded_bytes, start_index+35)[0]
        
        return LiquidityPoolData(TradeEventType.NEW_MINT, init_pc_amount, init_coin_amount)

    @staticmethod
    def parse_base58_data_withdraw_liquidity(start_index: int, decoded_bytes: bytes)->WithdrawLiquidity:
        lp_token_amount = struct.unpack_from('<Q', decoded_bytes, start_index+1)[0]

        return WithdrawLiquidity(lp_token_amount)
        
    @staticmethod
    def parse_base64_data_withdraw_liquidity(start_index: int, decoded_bytes: bytes)->WithdrawLiquidity:
        lp_token_amount = struct.unpack_from('<Q', decoded_bytes, start_index+1)[0]

        #FYI there's other info we could parse including outCoin and outPC        
        return WithdrawLiquidity(lp_token_amount)

    @staticmethod
    def parse_base64_data_add_liquidity(start_index: int, decoded_bytes: bytes)->LiquidityPoolData:     
        # Parse initPcAmount (8 bytes, u64)
        if len(decoded_bytes) >= 24:
            max_coin_amount = struct.unpack_from('<Q', decoded_bytes, start_index+1)[0]
            max_pc_amount = struct.unpack_from('<Q', decoded_bytes, start_index+9)[0]
            base_side = struct.unpack_from('<Q', decoded_bytes, start_index+17)[0]
        
            return LiquidityPoolData(TradeEventType.ADD_LIQUIDITY, max_pc_amount, max_coin_amount)
    
    @staticmethod
    def parse_base58_data_init2(start_index: int, decoded_bytes: bytes)->LiquidityPoolData:      
        # Parse the nonce (1 byte, u8)
        nonce = struct.unpack_from('B', decoded_bytes, start_index+1)[0]
        
        # Parse openTime (8 bytes, u64)
        open_time = struct.unpack_from('<Q', decoded_bytes, start_index+2)[0]  # '<Q' for little-endian unsigned long long (8 bytes)
        
        # Parse initPcAmount (8 bytes, u64)
        init_pc_amount = struct.unpack_from('<Q', decoded_bytes, start_index+10)[0]
        
        # Parse initCoinAmount (8 bytes, u64)
        init_coin_amount = struct.unpack_from('<Q', decoded_bytes, start_index+18)[0]
        
        return LiquidityPoolData(TradeEventType.NEW_MINT, init_pc_amount, init_coin_amount)

    @staticmethod
    def parse_base58_data_swapv2(start_index: int, decoded_bytes: bytes)->AmmSwapData:
        # Parse amountIn (8 bytes, u64)
        amount_in = struct.unpack_from('<Q', decoded_bytes, start_index+1)[0]  # '<Q' for little-endian unsigned long long (8 bytes)
                
        # Parse minimumAmountOut (8 bytes, u64)
        minimum_amount_out = struct.unpack_from('<Q', decoded_bytes, start_index+9)[0]

        return AmmSwapData(TradeEventType.EXCHANGE, amount_in, minimum_amount_out)

    #Data formats below for reference
    #Event Data
    #[{"name":"swapBaseIn","data":{"logType":{"type":"u8","data":3},"amountIn":{"type":"u64","data":"1712649245"},"minimumAmountOut":{"type":"u64","data":"57400494618"},"direction":{"type":"u64","data":"2"},"userSource":{"type":"u64","data":"541401452661"},"poolCoin":{"type":"u64","data":"761399143179"},"poolPc":{"type":"u64","data":"25877138710113"},"outAmount":{"type":"u64","data":"57931110978"}}}]
    #initialize2_format = {
    #    "discriminator": {
    #        "type": "u8",
    #        "data": 1
    #    },
    #    "nonce": {
    #        "type": "u8",
    #        "data": 254
    #    },
    #    "openTime": {
    #        "type": "u64",
    #        "data": "1736479444"
    #    },
    #    "initPcAmount": {
    #        "type": "u64",
    #        "data": "1000000000"
    #    },
    #    "initCoinAmount": {
    #        "type": "u64",
    #        "data": "50000000000000"
    #    }
    #}
#
    #swap_data_format = {
    #    "discriminator": {
    #        "type": "u8",
    #        "data": 9
    #    },
    #    "amountIn": {
    #        "type": "u64",
    #        "data": "8709997127"
    #    },
    #    "minimumAmountOut": {
    #        "type": "u64",
    #        "data": "96798496"
    #    }
    #}
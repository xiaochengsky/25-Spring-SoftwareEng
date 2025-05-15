from solders.pubkey import Pubkey
import struct
from MessageDecoder import LogsDecoder
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import *
   
class DataType(Enum):
    BYTE = 0
    UINT16 = 1
    UINT32 = 2
    INT32 = 3
    FLOAT32 = 4
    INT64 = 5
    UINT64 = 6
    FLOAT64 = 7
    PUBKEY = 8

class DataSpec:
    def __init__(self, format: str, size: int, is_little_endian: bool):
        if is_little_endian:
            endianness = "<"
        else:
            endianness = ">"

        self.format = endianness + format
        self.size = size

class DataSpecContainer:
    spec_mapping = {DataType.BYTE : DataSpec("B", 1, True), 
                    DataType.UINT16 : DataSpec("H", 4, True),
                    DataType.UINT32 : DataSpec("I", 4, True),
                    DataType.INT32 : DataSpec("i", 4, True),
                    DataType.FLOAT32 : DataSpec("f", 8, True),
                    DataType.INT64 : DataSpec("q", 8, True),
                    DataType.UINT64 : DataSpec("Q", 8, True),
                    DataType.FLOAT64 : DataSpec("d", 8, True),
                    DataType.PUBKEY : DataSpec("NA", 32, True)
                    }
    
    def __init__(self, spec_list: list[DataType]):
        self.spec_list = spec_list
        self.size = 0

        for data_type in spec_list:
            self.size += self.spec_mapping.get(data_type).size

    def decode(self, start_index: int, data: bytes)->list[any]:
        if len(data) < self.size:
            return 
        
        offset = start_index
        ret_list : list[ int | float ] = []

        for element in self.spec_list:
            spec = self.spec_mapping.get(element)

            if element != DataType.PUBKEY:
                decoded_value = struct.unpack_from(spec.format, data, offset)[0]
            else:
                decoded_value = Pubkey(data[offset:offset+32])

            ret_list.append(decoded_value)
            offset += spec.size

        return ret_list

deposit_message_types = [
    DataType.UINT64,
    DataType.UINT64,
    DataType.UINT64
]

logs_deposit_message_types = [
    DataType.INT64, #timestamp
    DataType.UINT64, #lp_token_amount_out
    DataType.UINT64, #max_base_amount_in
    DataType.UINT64, #max_quote_amount_in
    DataType.UINT64, #user_base_token_reserves
    DataType.UINT64, #user_quote_token_reserves
    DataType.UINT64, #pool_base_token_reserves
    DataType.UINT64, #pool_quote_token_reserves
    DataType.UINT64, #base_amount_in
    DataType.UINT64, #quote_amount_in
    DataType.UINT64, #lp_mint_supply
    DataType.PUBKEY, #pool
    DataType.PUBKEY, #user
    DataType.PUBKEY, #user_base_token_account
    DataType.PUBKEY, #user_quote_token_account
    DataType.PUBKEY, #user_pool_token_account
]

class PumpAmmDataDecoder(LogsDecoder):
    total_bonded = 0
    bonding_token_amount = 2069E11
    log_data_prefixes = [LogsDecoder.program_data_prefix, LogsDecoder.program_instruction_prefix]
    program_data_index = len(LogsDecoder.program_data_prefix)
    buy_discriminator = 0x66063D1201DAEBEA
    sell_discriminator = 0x33E685A4017F83AD
    add_liquidity_discriminator = 0xE992D18ECF6840BC
    deposit_discriminator = 0xf223c68952e1f2b6
    remove_liquidity_id = 0xB712469C946DA122
    cpi_log_info = 0xe445a52e51cb9a1d
    pool_account_discriminator = 0xF19A6D0411B16DBC
    log_create_discriminator = 0xB1310CD2A076A774
    log_deposit_discriminator = 0x78f83d531f8e6b90
    log_buy_discriminator = 0x67F4521F2CF57777
    log_sell_discriminator = 0x3E2F370AA503DC2A
    log_withdraw_discriminator = 0x1609851AA02C47C0
    deposit_spec = DataSpecContainer(deposit_message_types)
    logs_deposit_spec = DataSpecContainer(logs_deposit_message_types)

    def __init__(self, program_address: str, encoding: str):
        self.program_address = program_address
        self.encoding = encoding
        self.last_event = None
        
    def get_log_data_prefixes(self):
        return PumpAmmDataDecoder.log_data_prefixes
    
    def decode_log(self, log: str)->InstructionData:
        if log.startswith(LogsDecoder.program_data_prefix):   
            program_data = log[self.program_data_index:]
            program_data = program_data.strip()

            decoded_bytes = self.get_bytes(program_data, LogsDecoder.base64_encoding)
    
            return self.decode_bytes_data(decoded_bytes)

    @staticmethod
    def parse_account_message(start_index: int, data: bytes)->LiquidityPoolData:
        offset = start_index
        pool_bump = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        index = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        creator = Pubkey(data[offset:offset+32])
        offset += 32
        base_mint = Pubkey(data[offset:offset+32])
        offset += 32
        quote_mint = Pubkey(data[offset:offset+32])
        offset += 32
        lp_mint = Pubkey(data[offset:offset+32])
        offset += 32
        pool_base_token_account = Pubkey(data[offset:offset+32])
        offset += 32
        pool_quote_token_account = Pubkey(data[offset:offset+32])
        offset += 32
        lp_supply = struct.unpack_from('<Q', data, offset)[0]
        
        ret_data = LiquidityPoolData(TradeEventType.ACCOUNT_INFO, 0, 0)
        ret_data.token_address = str(base_mint)
        ret_data.trader_address = str(creator)
        ret_data.pool_base_address = str(pool_base_token_account)
        ret_data.pool_quote_address = str(pool_quote_token_account)
        ret_data.quote_mint_address = str(quote_mint)
        ret_data.lp_supply = lp_supply        

        return ret_data
    
    @staticmethod
    def parse_logs_deposit_message(start_index: int, data: bytes)->LiquidityPoolData:
        offset = start_index

        decoded_data = PumpAmmDataDecoder.logs_deposit_spec.decode(offset, data)

        if decoded_data:
            timestamp = decoded_data[0]
            lpTokenAmountOut = decoded_data[1]
            max_base_amount_in = decoded_data[2]
            max_quote_amount_in = decoded_data[3]
            user_base_token_reserves = decoded_data[4]
            user_quote_token_reserves = decoded_data[5]
            pool_base_token_reserves = decoded_data[6]
            pool_quote_token_reserves = decoded_data[7]
            base_amount_in = decoded_data[8]
            quote_amount_in = decoded_data[9]
            lp_mint_supply = decoded_data[10]
            pool = decoded_data[11]
            user = decoded_data[12]
            user_base_token_account = decoded_data[13]
            user_quote_token_account = decoded_data[14]
            user_pool_token_account = decoded_data[15]

            ret_data = LiquidityPoolData(TradeEventType.DEPOSIT_LIQUIDITY, user_quote_token_reserves, user_base_token_reserves)
            ret_data.market_address = str(pool) #This message is missing a lot of vital data including the mint address; will have to derive it later from this

            return ret_data
    
    @staticmethod
    def parse_create_message(start_index: int, data: bytes)->LiquidityPoolData:
        offset = start_index

        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        index = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        creator = Pubkey(data[offset:offset+32])
        offset += 32
        baseMint = Pubkey(data[offset:offset+32])
        offset += 32
        quoteMint = Pubkey(data[offset:offset+32])
        offset += 32
        baseMintDecimals = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        quoteMintDecimals = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        baseAmountIn = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        quoteAmountIn = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        poolBaseAmount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        poolQuoteAmount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        minimumLiquidity = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        initialLiquidity = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        lpTokenAmountOut = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        poolBump = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        pool = Pubkey(data[offset:offset+32])
        offset += 32
        lpMint = Pubkey(data[offset:offset+32])
        offset += 32
        userBaseTokenAccount = Pubkey(data[offset:offset+32])
        offset += 32
        userQuoteTokenAccount = Pubkey(data[offset:offset+32])
        
        ret_data = LiquidityPoolData(TradeEventType.ADD_LIQUIDITY, poolQuoteAmount, poolBaseAmount)
        ret_data.market_address = str(pool)
        ret_data.trader_address = str(creator)
        ret_data.base_mint_address = str(baseMint)
        ret_data.quote_mint_address = str(quoteMint)
        #ret_data.pool_base_address = None
        #ret_data.pool_quote_address = None #Not here
        ret_data.lp_mint_address = str(lpMint)
        ret_data.base_mint_decimals = baseMintDecimals
        ret_data.quote_mint_decimals = quoteMintDecimals
        return ret_data
    
    #TODO load these from specs to cleanup the code; this is what the idls are for
    @staticmethod
    def parse_exchange_message(is_buy: bool, start_index: int, data: bytes)->LiquidityPoolData:
        offset = start_index

        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        base_amount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        slippage_quote_amount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        user_base_token_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        user_quote_token_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        pool_base_token_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        pool_quote_token_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        quote_amount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        lp_fee_basis_points = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        lp_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        protocol_fee_basis_points = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        protocol_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        quote_amount_with_lp_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        user_quote_amount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        pool = Pubkey(data[offset:offset+32])
        offset += 32

        user = Pubkey(data[offset:offset+32])
        offset += 32

        user_base_token_account = Pubkey(data[offset:offset+32])
        offset += 32
       
        user_quote_token_account = Pubkey(data[offset:offset+32])
        offset += 32

        protocol_fee_recipient = Pubkey(data[offset:offset+32])
        offset += 32

        protocol_fee_recipient_token_account = Pubkey(data[offset:offset+32])

        if is_buy:
            trade_type = TradeEventType.BUY
            amount_in = quote_amount
            amount_out = base_amount
        else:
            trade_type = TradeEventType.SELL
            amount_in = base_amount 
            amount_out = quote_amount

        ret_data = AmmSwapData(trade_type, amount_in, amount_out)

        return ret_data
    
    def parse_pump_bytes(self, data: bytes)->InstructionData:
        offset = 0
        ret_data = None

        discriminator = struct.unpack_from('>Q', data, offset)[0]
        offset += 8

        if discriminator == self.add_liquidity_discriminator:
            #index = struct.unpack_from('<B', data, offset)[0]
            offset += 2

            # Parse initPcAmount (8 bytes, u64)
            init_coin_amount = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            # Parse initCoinAmount (8 bytes, u64)
            init_pc_amount = struct.unpack_from('<Q', data, offset)[0]
            ret_data = LiquidityPoolData(TradeEventType.ADD_LIQUIDITY, init_pc_amount, init_coin_amount)

            if init_pc_amount >= self.bonding_token_amount:
                self.total_bonded += 1
                print(f"Add Liquidity Pump Token: PC: {init_pc_amount} Coin: {init_coin_amount} total: {self.total_bonded}")
        elif discriminator == self.remove_liquidity_id:
            #index = struct.unpack_from('<B', data, offset)[0]
            offset += 2
        elif discriminator == self.buy_discriminator or discriminator == self.sell_discriminator:
            # Parse amountIn (8 bytes, u64)
            amount_base = struct.unpack_from('<Q', data, offset)[0]  # '<Q' for little-endian unsigned long long (8 bytes)
            offset += 8        
            # Parse minimumAmountOut (8 bytes, u64)
            quote_amount = struct.unpack_from('<Q', data, offset)[0]

            if discriminator == self.buy_discriminator:
                event_type = TradeEventType.BUY
                amount_in = quote_amount
                amount_out = amount_base
            else:
                event_type = TradeEventType.SELL
                amount_in = amount_base
                amount_out = quote_amount

            ret_data = AmmSwapData(event_type, amount_in, amount_out)

        else:
            if discriminator == self.cpi_log_info:
                discriminator = struct.unpack_from('>Q', data, offset)[0]  # Type
                offset += 8 #Entire discriminator is really 8 bytes
            
            if discriminator == self.log_create_discriminator:
                ret_data = self.parse_create_message(offset, data)
            elif discriminator == self.pool_account_discriminator:
                ret_data = self.parse_account_message(offset, data)
            elif discriminator == self.log_buy_discriminator:
                ret_data = self.parse_exchange_message(True, offset, data)
            elif discriminator == self.log_sell_discriminator:    
                ret_data = self.parse_exchange_message(False, offset, data)
            elif discriminator == self.log_deposit_discriminator:
                ret_data = self.parse_logs_deposit_message(offset, data)    

        if ret_data:
            ret_data.program_type = SupportedPrograms.PUMPFUN_AMM
            return ret_data
    
    def decode_bytes_data(self, data: bytes)->InstructionData:
        ret_data = None
       
        try:
            ret_data = self.parse_pump_bytes(data)    
        except Exception as e:
            print("PumpAmmDataDecoder: Bad data " + data.hex())   
        
        return ret_data

    def decode(self, program_data: dict)->InstructionData:   
        instruction_data = program_data.get('data')
        encoding = self.encoding

        if isinstance(instruction_data, list) and len(instruction_data) >= 2: #remove check if confident
            encoding = instruction_data[1]
            instruction_data = instruction_data[0]
                
        if instruction_data:
            decoded_bytes = self.get_bytes(instruction_data, encoding) 
        
            ret_object = self.decode_bytes_data(decoded_bytes)      
            
            #Create a filled out MintMetadata object
            if ret_object:
                instruction_accounts = program_data.get('accounts')

                if instruction_accounts:
                    if (len(instruction_accounts) > 10 and isinstance(ret_object, LiquidityPoolData) and 
                        (ret_object.get_type() == TradeEventType.ADD_LIQUIDITY or ret_object.get_type() == TradeEventType.DEPOSIT_LIQUIDITY)):                                         
                        #Fill out the rest of it
                        import time
                        print("Pump AMM Added Liquidity: " + instruction_accounts[0] + " " + str(time.time_ns())) #DELETE THIS
                        ret_object.market_address = instruction_accounts[0]
                        ret_object.trader_address = instruction_accounts[2]
                        ret_object.base_mint_address = instruction_accounts[3]
                        ret_object.quote_mint_address = instruction_accounts[4]
                        ret_object.lp_mint_address = instruction_accounts[5]
                        ret_object.pool_base_address = instruction_accounts[9]
                        ret_object.pool_quote_address = instruction_accounts[10]
                        ret_object.token_address = ret_object.base_mint_address

                    elif len(instruction_accounts) > 10 and ret_object.get_type() == TradeEventType.REMOVE_LIQUIDITY:
                        pass #TODO
                    elif isinstance(ret_object, AmmSwapData):
                        ret_object.market_address = instruction_accounts[0]
                        ret_object.token_address = instruction_accounts[3]
                    
                        #Set vault accounts                 
                        ret_object.pool_base_address = instruction_accounts[7]
                        ret_object.pool_quote_address = instruction_accounts[8]
            
            return ret_object
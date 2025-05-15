from enum import Enum

class TableType(Enum):
    PUMP_PENDING_VIEW = 0
    COMPLETED_VIEW = 1
    WATCHING_VIEW = 2
    WALLET_VIEW = 3
    BONDED_PENDING_VIEW = 4

class TokenPhase(Enum):
    NEW_MINT = 0
    NOT_BONDED = 1
    BONDING_IN_PROGRESS = 2
    BONDED = 3

class Blockchain(Enum):
    SOL = 1
    
    @staticmethod
    def to_enum(type_str: str)->Enum:
        if type_str.upper() == Blockchain.SOL.name:
            return Blockchain.SOL

class Denomination(Enum):
    USD = 0
    SOL = 1
    
class TradeRecommendation(Enum):
    SELL = 1
    BUY = 2
    HOLD = 3
    SELL_TAKE_PROFIT = 4
    SELL_CUT_LOSSES = 5

#TODO change name to TransactionEventType
class TradeEventType(Enum):
    SIGNAL = 0
    PNL = 1
    CUSTOM_STRATEGY = 2
    SIMPLE_BUY_DIP_STRATEGY = 4
    NEW_MINT = 5
    NOT_BONDED = 6
    WATCHED_WALLET_CHANGE = 7
    EXCHANGE = 8
    BONDING_COMPLETE = 9
    ADD_LIQUIDITY = 10
    REMOVE_LIQUIDITY = 11
    BUY = 12 
    SELL = 13
    SELL_ALL = 14 
    SOL_TRANSFER = 15
    TOKEN_TRANSFER = 16
    DATA = 17
    CREATE = 18
    UNDEFINED = 19
    LO_PENDING_SELL = 20
    ACCOUNT_INFO = 21
    DEPOSIT_LIQUIDITY = 22
    
    @staticmethod
    def to_enum(type_str: str)->Enum:
        if type_str == "transfer":
            return TradeEventType.SOL_TRANSFER
        elif type_str == 'transferChecked':
            return TradeEventType.TOKEN_TRANSFER
        elif type_str == "buy":
            return TradeEventType.BUY
        elif type_str == "sell":
            return TradeEventType.SELL
        else:
            return TradeEventType.UNDEFINED        

class AlertReason(Enum):
    PROFIT_LIMIT = 0
    LOSS_LIMIT = 1
    DEV_JEETED = 2
    SIGNIFICANT_DUMP = 3
    VOLUMEUP = 4
    VOLUMEDOWN = 5
    FORCED = 6
    RISK_HIGH = 7
    NOT_ENOUGH_SOL = 8
    GENERAL = 9
    WatchedWalletEvent = 10

    def to_string(reason):
        switcher = {
            0: "PROFIT_LIMIT",
            1: "LOSS_LIMIT",
            2: "DEV_JEETED",
            3: "SIGNIFICANT_DUMP",
            4: "VOLUMEUP",
            5: "VOLUMEDOWN",
            6: "FORCED",
        }
    
        if (isinstance(reason.value, tuple) or isinstance(reason.value, set)) and len(reason.value) > 0:
            value = reason.value[0]
        else:
            value = reason.value

        return switcher.get(value, "nothing")

class SupportedPrograms(Enum):
    PUMPFUN = 0
    PUMPFUN_AMM = 1
    RAYDIUMLEGACY = 2
    GENERAL_WALLET = 3
    WATCHER_WALLET = 4
    ALL = 5
    
    @staticmethod
    def string_to_enum(program_name: str):
        upper_name = str.upper(program_name)
        
        if upper_name == SupportedPrograms.PUMPFUN.name:
            return SupportedPrograms.PUMPFUN
        elif upper_name == SupportedPrograms.RAYDIUMLEGACY.name:
            return SupportedPrograms.RAYDIUMLEGACY
        
class StrategyState(Enum):
    PENDING = 0,
    COMPLETE = 1,
    FAILED = 2

class SignalState(Enum):
    TRIGGERED = 0,
    UNTRIGGERED = 1

class Value_Type(Enum):
    UI = 0
    SCALED = 1

class Amount_Units:
    SOL = 0
    USD = 1
    TOKENS = 2
    PERCENT = 3
    
class UI_Command(Enum):
    FORCE_ADD_TOKEN = 0
    BUY = 1
    SELL = 2
    SWEEP = 3
    HOLD = 4
    SELL_ALL = 5
    DELETE = 6

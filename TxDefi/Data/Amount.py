from TxDefi.Data.MarketEnums import *
import TxDefi.DataAccess.Blockchains.Solana.SolanaUtilities as solana_utilites

class Amount:
    def __init__(self, value_type: Value_Type, amount_units: Amount_Units, amount: float, decimals: int):
        self.value_type = value_type
        self.amount_units = amount_units
        self.value = amount
        self.decimals = decimals
        self.scalar = 10**decimals
    
    def set_amount(self, amount: "Amount"):
        self.value_type = amount.value_type
        self.amount_units = amount.amount_units
        self.value = amount.amount
        self.scalar = amount.scalar

    def set_amount2(self, amount: float, value_type: Value_Type):
        if value_type == self.value_type:
            self.value = amount
        elif self.value_type == Value_Type.SCALED:
            self.value = amount*self.scalar
        else:
            self.value = amount/self.scalar

    def add_amount(self, amount: float, value_type: Value_Type):
        if value_type == self.value_type:
            self.value += amount
        elif value_type == Value_Type.SCALED:
            self.value += amount/self.scalar
        else:
            self.value += amount*self.scalar

    def compare(self, amount: "Amount")->float:        
        if amount.value_type == self.value_type:
            self_diff = self.value - amount.value
        elif self.value_type == Value_Type.SCALED:
            self_diff = self.value - amount.to_scaled()
        else:
            self_diff = self.value - amount.to_ui()
        
        return self_diff
    
    def to_ui(self)->float:
        ret_value = self.value
        
        if self.value_type == Value_Type.SCALED:
            ret_value /= self.scalar

        return ret_value
    
    def to_string(self)->str:
        return str(self.to_ui())
    
    def to_scaled(self)->int:
        if self.value_type == Value_Type.SCALED:
            return self.value
        else:
            return int(self.value*self.scalar)
        
    def clone(self)->"Amount":
        return Amount(self.value_type, self.amount_units, self.value, self.decimals)
    
    def get_scalar(self)->float:
        return self.scalar

    def to_string(self, rounding = 0)->str:
        value = self.to_ui()

        if rounding > 0:
           value = round(value, rounding)

        return str(value)
    
    @staticmethod
    def sol_ui(amount: float):
        return Amount(Value_Type.UI, Amount_Units.SOL, amount, solana_utilites.SOL_DECIMALS)

    @staticmethod
    def sol_scaled(amount: int):
        return Amount(Value_Type.SCALED, Amount_Units.SOL, int(amount), solana_utilites.SOL_DECIMALS)
    
    @staticmethod
    def tokens_ui(amount: float, decimals: int):
        return Amount(Value_Type.UI, Amount_Units.TOKENS, amount, decimals)

    @staticmethod
    def tokens_scaled(amount: float, decimals: int):
        return Amount(Value_Type.SCALED, Amount_Units.TOKENS, amount, decimals)
    
    @staticmethod
    def percent_ui(amount: float):
        return Amount(Value_Type.UI, Amount_Units.PERCENT, amount, 2) #scale factor is 100 for scaled bps

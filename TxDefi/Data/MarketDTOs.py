from TxDefi.Data.MarketEnums import *
from TxDefi.Data.Amount import *
from TxDefi.Data.TransactionInfo import *

class RecommendResult:
    def __init__(self, recommendation: TradeRecommendation, tokenQuantity: float, msg: str):
        self.recommendation = recommendation
        self.tokenQuantity = tokenQuantity
        self.msg = msg

    def to_string(self):
        return f"{str(self.recommendation)} - Token Quantity: {self.tokenQuantity} Msg: {self.msg}\n"

    def is_sell(self):
        return (self.recommendation == TradeRecommendation.SELL or self.recommendation == TradeRecommendation.SELL_CUT_LOSSES or 
            self.recommendation == TradeRecommendation.SELL_TAKE_PROFIT)

class MarketAlert:
    def __init__(self, token_address: str, info_type: TradeEventType, supported_pg_type : SupportedPrograms = None):
        self.token_address = token_address
        self.info_type = info_type
        self.program_type  = supported_pg_type

    def get_type(self):
        return self.info_type

    def get_program_type(self):
        return self.program_type
    
class LiquidityPoolAlert(MarketAlert):
    def __init__(self, pool_data: LiquidityPoolData):
        MarketAlert.__init__(self, pool_data.token_address, pool_data.get_type())
        self.pool_data = pool_data

class RetailTransaction(MarketAlert):
    def __init__(self, mintAddress: str):
        MarketAlert.__init__(self, mintAddress, TradeEventType.EXCHANGE) 
        self.is_buy = False
        self.trader_address = ""
        self.trade_amt_sol = 0
        self.token_quantity = 0 
        self.transaction_timestamp = 0
        self.sol_reserves = 0
        self.token_reserves = 0
        self.payerPrice = 0
        self.tx_signature = ""
        
    def to_string(self):
        return f"Retail Transaction: {self.trader_address} exchanged {self.mint_address} {str(self.trade_amt_sol/solana_utilites.SOL_SCALE_FACTOR)}"

class ProfitLoss(MarketAlert):
  def __init__(self, token_address: str, pnl: Amount, pnl_percent: Amount, cost_basis: Amount, token_quantity: Amount, is_complete: bool):
        MarketAlert.__init__(self, token_address, TradeEventType.PNL)
        self.pnl = pnl
        self.pnl_percent = pnl_percent
        self.is_complete = is_complete
        self.cost_basis = cost_basis
        self.token_quantity = token_quantity
        self.tx_signature = "" #Optional

class MintMetadata(MarketAlert): #Deprecate and just use ExtendedMetadata
    def __init__(self, token_address: str):
        MarketAlert.__init__(self, token_address, TradeEventType.NEW_MINT)
        self.token_address = token_address
        self.token_program_address = ""
        self.program_id = ""
        self.name = ""
        self.symbol = ""       
        self.sol_vault_address = ""   
        self.token_vault_address = ""
        self.creator_address = ""
        self.description = ""
        self.image_uri = ""
        self.created_on = ""
        self.inner_metadata_uri = ""
        self.market_id = ''
        self.quoted_currency_address = ''
        self.token_decimals = 0

        self.freeze_authority = None
        self.mint_authority = None
        self.owner_address = ""
    
    def to_string(self):
        return f"{self.creator_address} created {self.token_address}"

    def from_json(self, primaryJson, supplementalJson):
        pData = primaryJson
        sData = supplementalJson
        
        self.description = pData['content']['metadata']['description']
        self.name = pData['content']['metadata']['name']
        self.symbol = pData['content']['metadata']['symbol']
        
        self.created_on = sData['createdOn']             

    def from_dict(self, valuesDict):        
        self.name = valuesDict['name']
        self.program_id = valuesDict['programId']
        self.symbol = valuesDict['symbol']  
        self.token_address = valuesDict['mintAddress']    
        self.sol_vault_address = valuesDict['bondingCurve']
        self.token_vault_address = valuesDict['associatedBondingCurve']
        self.creator_address = valuesDict['creatorAddress']
        self.description = valuesDict['description']
        self.image_uri = valuesDict['imageUri']
        self.telegram = valuesDict['telegram']
        self.twitter = valuesDict['twitter']
        self.website = valuesDict['website']
        self.created_on = valuesDict['createdOn']
        self.origin_url = valuesDict['url']

    def to_dict(self):
        return self.__dict__

class ExtendedMetadata(MintMetadata):
    def __init__(self, token_address: str):
        MintMetadata.__init__(self, token_address)
        self.open_graph_url = ''
        self.banner_url = ''
        self.is_mutable = False
        self.supply : Amount = None
        self.socials : Socials = Socials() 

#TODO Far future work: Refactor to use Amount for all classes below
class TokenInfo:
    def __init__(self, token_address: str, decimals: int):
        self.metadata = ExtendedMetadata(token_address)
        self.metadata.token_decimals = decimals
        self.token_address = token_address
        self.ui_price = Amount.sol_ui(0) #set if vault amounts are unavailable
        self.sol_vault_amount = Amount.sol_ui(0)
        self.token_vault_amount = Amount.tokens_ui(0, decimals)
        self.metadata.supply = Amount.tokens_ui(0, decimals)
        self.phase = TokenPhase.BONDED

    def get_price(self)->Amount:
        if self.token_vault_amount.value > 0: #only use if set 
            ret_amount = self.sol_vault_amount.to_ui()/self.token_vault_amount.to_ui()
            self.ui_price.set_amount2(ret_amount, Value_Type.UI) #Keep price updated
            
        return self.ui_price
    
    def is_metadata_complete(self):
        return len(self.metadata.sol_vault_address) > 0 and len(self.metadata.token_vault_address) > 0 #TODO Add more checks if needed
    
    def copy_missing(self, token_info: "TokenInfo"):
        if self.token_vault_amount.value <= 0:
            self.token_vault_amount = token_info.token_vault_amount
    
        if self.sol_vault_amount.value <= 0:
            self.sol_vault_amount = token_info.sol_vault_amount

        self.copy_missing_metadata(token_info.metadata)

        #Do the rest

    def copy_missing_metadata(self, metadata: ExtendedMetadata):
        if len(self.metadata.sol_vault_address) == 0:
            self.metadata.sol_vault_address =  metadata.sol_vault_address
    
        if len(self.metadata.token_vault_address) == 0:
            self.metadata.token_vault_address = metadata.token_vault_address
    
        if self.metadata.token_decimals <= 0:
            self.metadata.token_decimals =  metadata.token_decimals

        if not self.metadata.supply or self.metadata.supply.value == 0:
            self.metadata.supply = metadata.supply

        if len(self.metadata.inner_metadata_uri) == 0:
            self.metadata.inner_metadata_uri = metadata.inner_metadata_uri

        if len(self.metadata.image_uri) == 0:
            self.metadata.image_uri = metadata.image_uri
        
        if len(self.metadata.name) == 0:
            self.metadata.name = metadata.name

        if len(self.metadata.symbol) == 0:
            self.metadata.symbol = metadata.symbol
    
        if len(self.metadata.created_on) == 0:
            self.metadata.created_on = metadata.created_on
    
        if not self.metadata.socials or self.metadata.socials.num_socials() == 0:
            self.metadata.socials = metadata.socials

        if len(self.metadata.token_program_address) == 0:
            self.metadata.token_program_address = metadata.token_program_address

        #FYI could be more to copy later

    @staticmethod
    def from_metadata(mint_data: "ExtendedMetadata")->"TokenInfo":
        ret_token_info = TokenInfo(mint_data.token_address, mint_data.token_decimals)
        ret_token_info.metadata = mint_data
        return ret_token_info
    
    @staticmethod
    def create(program_type: SupportedPrograms, token_address: str, sol_vault_address: str, token_vault_address: str, 
               init_sol_amount: Amount, init_token_amount: Amount, decimals: int)->"TokenInfo":
        ret_token_info = TokenInfo(token_address, decimals)

        ret_token_info.metadata = ExtendedMetadata(token_address)    
        ret_token_info.metadata.program_type = program_type
        ret_token_info.metadata.sol_vault_address = sol_vault_address
        ret_token_info.metadata.token_vault_address = token_vault_address
        ret_token_info.sol_vault_amount = init_sol_amount
        ret_token_info.token_vault_amount = init_token_amount
        ret_token_info.metadata.supply = Amount.tokens_ui(0, decimals)

        if program_type == SupportedPrograms.PUMPFUN:
            ret_token_info.phase = TokenPhase.NOT_BONDED

        return ret_token_info

class WalletEvent(MarketAlert):
     def __init__(self, retailTransaction: RetailTransaction, eventType = TradeEventType.WATCHED_WALLET_CHANGE):
        MarketAlert.__init__(self, retailTransaction.mint_address, eventType)
        self.retailTransaction = retailTransaction

class TradeSignal(MarketAlert):
       def __init__(self, mintAddress: str, message: str, eventType: AlertReason):
           MarketAlert.__init__(self, mintAddress, eventType)
           self.message = message

class BuySignal(TradeSignal):
    def __init__(self, mintAddress: str, message: str, eventType: AlertReason):
        TradeSignal.__init__(self, mintAddress, message, eventType)

class SellSignal(TradeSignal):
    def __init__(self, mintAddress: str, message: str, eventType: AlertReason, tokenQuantity = 0):
        TradeSignal.__init__(self, mintAddress, message, eventType)
        self.tokenQuantity = tokenQuantity

class TokenValue:
    def __init__(self, token_address: str, price: Amount, market_cap: Amount):
        self.token_address = token_address
        self.price = price
        self.market_cap = market_cap

    @staticmethod
    def string_format(value: float)->str:
        return "{:,}".format(value)
    
class Socials:
    supported_socials = ['twitter', 'telegram', 'website'] 

    def __init__(self):
        self.uris : dict[str, str] = {}

    def update(self, name: str, social_uri: str):
        self.uris[name] = social_uri

    def get_uri(self, name: str)-> str:
        return self.uris.get(name, '')

    def num_socials(self)->int:
        return len(self.uris)
    
    def to_string(self)->str:     
        socials_text = ""
        
        if len(self.uris) > 0:
            values_list = list(self.uris.values())
            for i in range(len(values_list)):
                if values_list[i] and len(values_list[i]) > 0:
                    socials_text += values_list[i] 

                    if i < len(values_list)-1:
                        socials_text += "\n"
        
        return socials_text

class TradeStatus:
    def __init__(self, token_info: TokenInfo, trade_event: TradeEventType):
        self.token_info = token_info
        self.event_type = trade_event

    def get_type(self):
        self.event_type

class TradeInfo(MarketAlert):
    def __init__(self, token_info: TokenInfo, trade_event: TradeEventType, amount_in: Amount, amount_out: Amount, fee: Amount, tx_signature: str):
        MarketAlert.__init__(self, token_info.token_address, trade_event, token_info.metadata.program_type)
        self.token_info = token_info
        self.fee = fee
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.tx_signature = tx_signature

    def get_price(self)->Amount:
        #Rough Price TODO include fees
        if self.amount_in.amount_units == Amount_Units.TOKENS:   
            sol_amount = self.amount_out.to_ui()+self.fee.to_ui()
            amount_ui = sol_amount/self.amount_in.to_ui()
        else:            
            sol_amount = self.amount_in.to_ui()-self.fee.to_ui()
            amount_ui = sol_amount/self.amount_out.to_ui()
        
        return Amount.sol_ui(amount_ui)
    
    @staticmethod
    def create(token_info: TokenInfo, trade_event: TradeEventType, tx_signature: str)->"TokenInfo":
        return TradeInfo(token_info, trade_event, Amount.sol_ui(0), Amount.tokens_ui(0, token_info.metadata.token_decimals), Amount.sol_ui(0), tx_signature)

#if __name__ == '__main__':
#    solReserves = 34035634837
#    tokenReserves = 945773473607611
#    
#    meta = MintMetadata("affaafda")
#    
#    meta.creator_address = "affafnlkdalk"
#    mInfo = MarketInfo(MintMetadata("affaafda"), solReserves, tokenReserves, 2e9, 1000e6)
#
#    jsonString = su.serialize(mInfo)    
#
#    buyAmount = 5*solana_utilites.SOL_SCALE_FACTOR
#    result =  FinanceUtil.est_exchange_reserves(solReserves, tokenReserves, buyAmount)
#    solReserves = result['reserves_a']
#    tokenReserves = result['reserves_b']
#    tokensBought = result['tokens_receivable']
#
#    print("Bought: " + str(tokensBought) + " with " + str(buyAmount) +  " lamports")
#
#    #Sell Back
#    result =  FinanceUtil.est_exchange_reserves(tokenReserves, solReserves, tokensBought*.5)
#    print("Sold: " + str(tokensBought) + " received " + str(result['tokens_receivable']) +  " lamports")
#
   
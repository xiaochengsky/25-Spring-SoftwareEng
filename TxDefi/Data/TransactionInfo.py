from Amount import Amount
from TxDefi.Data.MarketEnums import *
from TxDefi.Data.TransactionInfo import *
import TxDefi.DataAccess.Blockchains.Solana.SolanaUtilities as solana_utilites

class InstructionData:
    def __init__(self, info_type: TradeEventType):
        self.info_type = info_type
        self.slot = 0
        self.tx_signature = ''
        self.program_type : SupportedPrograms = None
    
    def get_type(self)->TradeEventType:
        return self.info_type
    
    def to_string(self):
        return self.info_type.name

class PumpMigration(InstructionData):
    def __init__(self, token_address: str):
        InstructionData.__init__(self, TradeEventType.BONDING_COMPLETE)
        self.token_address = token_address
        self.program_type = SupportedPrograms.PUMPFUN
        self.sol_vault_address = ""
        self.token_vault_address = ""
        self.market_address = ""
        self.lp_token_address = ""

class InstructionInfo:
    def __init__(self, instruction_type: TradeEventType, accounts: dict, data: InstructionData):
        self.instruction_type = instruction_type
        self.accounts = accounts
        self.data = data

class TransactionInfo:
   def __init__(self, tx_signature: str, slot: int):
       self.tx_signature = tx_signature
       self.slot = slot

class SwapData(InstructionData):
    def __init__(self, swap_type: TradeEventType, in_amount: int,  out_amount: int):
        InstructionData.__init__(self, swap_type)
        self.in_amount = in_amount
        self.out_amount = out_amount
        self.user_in_account = ""
        self.user_out_account = ""
        
class AmmSwapData(SwapData):
    def __init__(self, swap_type: TradeEventType, in_amount: int, out_amount: int):
        SwapData.__init__(self, swap_type, in_amount, out_amount)
        self.market_address = ""
        self.amm_authority_address = ""
        self.trader_address = ""
        self.token_address = ""
        self.pool_base_address = ""
        self.pool_quote_address = ""

class SwapRouteData(SwapData):
    def __init__(self, in_amount: int, out_amount: int, slippage_bps: int, platform_fee_bps: int):
        SwapData.__init__(self, TradeEventType.EXCHANGE, in_amount, out_amount)
        #TODO Add routes data if needed
        self.slippage_bps = slippage_bps
        self.platform_fee_bps = platform_fee_bps

class TransferData(InstructionData):
    def __init__(self, source: str, destination: str, lamports: int):
        InstructionData.__init__(self, TradeEventType.SOL_TRANSFER)
        self.source = source
        self.destination = destination
        self.lamports = lamports

    def to_string(self):
        return f"{self.info_type.name}: Lamports = {self.lamports} Source = {self.source} Destination = {self.destination}"
     
class ParsedTransaction(TransactionInfo):
    def __init__(self, signature: str, slot: int, payer_address: str, accounts: list[dict], pre_sol_balances: list[int],
                   post_sol_balances: list[int], pre_token_balances: dict, post_token_balances: dict, fees: int, instructions: list[InstructionInfo],
                     log_messages: list[str]):
        TransactionInfo.__init__(self, signature, slot)
        self.payer_address = payer_address
        self.accounts : list [str] = accounts
        self.pre_sol_balances : dict = pre_sol_balances
        self.post_sol_balances : dict = post_sol_balances
        self.pre_token_balances : dict = pre_token_balances
        self.post_token_balances : dict = post_token_balances
        self.fees = fees
        self.instructions = instructions
        self.log_messages = log_messages
        
    def get_supported_programs(self):
        ret_set : set[SupportedPrograms] = set()

        for instruction in self.instructions:
            if instruction.data.program_type not in ret_set and instruction.data.program_type is not None:
                ret_set.add(instruction.data.program_type)

        return ret_set

    def get_sol_balance(self, account_address: str):
        for i in range(len(self.accounts)):
            if account_address == str(self.accounts[i]['pubkey']) and i < len(self.post_sol_balances):
                return self.post_sol_balances[i]
            
    def get_pool_info(self, account_address: str)->dict[str, any]:
        for token_balance in self.post_token_balances:        
            account_index = token_balance['accountIndex']

            if account_index < len(self.accounts) and account_address == self.accounts[account_index]['pubkey']:
                return token_balance   
            
class SwapTransactionInfo(TransactionInfo):
    def __init__(self, tx_signature: str, slot: int):
        TransactionInfo.__init__(self, tx_signature, slot)
        self.token_address = ''
        self.payer_address = ''
        self.payer_token_account_address = ''
        self.fee = 0
        self.payer_token_ui_balance = 0
        self.sol_balance_change = 0 #scaled
        self.token_balance_change = 0 #ui amount
        self.token_decimals = 0
        
    def print_swap_info(self):
        sol_amount = str(abs(self.sol_balance_change)/solana_utilites.SOL_SCALE_FACTOR)
        token_amount = str(abs(self.token_balance_change))

        if self.sol_balance_change < 0:
            print(f"{self.payer_address} bought {token_amount} tokens for {sol_amount} SOL")
        else:
            print(f"{self.payer_address} sold {token_amount} tokens for {sol_amount} SOL")
            
class TokenAmount_json:
    def __init__(self, amount: str, decimals: str, ui_amount: int, ui_amount_string: str):
        self.amount = amount
        self.decimals = decimals
        self.ui_amount = ui_amount
        self.ui_amount_string = ui_amount_string

class TokenAccount_json:
    def __init__(self, account_index: int, owner_address: str, mint_address: str):
        self.account_index = account_index
        self.owner_address = owner_address
        self.mint_address = mint_address
        self.ui_balance = 0

class TransferCheckedData_json(InstructionData):
    def __init__(self, source: str, destination: str, mint: str, multisigAuthority: str, signers: list[str], token_amount: TokenAmount_json):
        InstructionData.__init__(self, TradeEventType.TOKEN_TRANSFER)
        self.source = source
        self.destination = destination
        self.mint = mint
        self.multisigAuthority = multisigAuthority
        self.signers = signers
        self.token_amount = token_amount

    def to_string(self):
        return f"{self.info_type.name}: Mint = {self.mint} Source = {self.source} Destination = {self.destination}"

class LiquidityPoolData(InstructionData):
    def __init__(self, info_type: TradeEventType, pc_amount: int, coin_amount: int):
        InstructionData.__init__(self, info_type)
        self.token_address = "" #TODO Deprecate, just use base_mint, raydium decoder still depends on this so leaving it alone for now
        self.pc_amount = pc_amount
        self.coin_amount = coin_amount
        self.amm_authority_address = ""
        self.trader_address = ""
        self.market_address = ""
        self.base_mint_address = ""
        self.quote_mint_address = ""
        self.pool_base_address = "" #vault
        self.pool_quote_address = "" #vault
        self.lp_mint_address = ""
        self.base_mint_decimals = 0
        self.quote_mint_decimals = 0
        self.total_supply = 0
        self.lp_supply = 0
    
class WithdrawLiquidity(LiquidityPoolData):
    def __init__(self, lp_token_amount : int):
        LiquidityPoolData.__init__(self, TradeEventType.REMOVE_LIQUIDITY, 0, 0)
        self.lp_amount_out = lp_token_amount

class AccountInfo:
    def __init__(self, account_address: str, balance: Amount, mint_address = solana_utilites.UNWRAPPED_SOL_MINT_ADDRESS, account_data: list[str] | dict = None):
        self.account_address = account_address
        self.mint_address = mint_address
        self.initial_balance = balance
        self.balance = balance.clone()
        self.last_slot = 0
        self.owned_accounts: dict[str, AccountInfo] = {}
        self.account_data = account_data

    def get_account(self, account_address: str):
        return  self.owned_accounts.get(account_address)
    
    def add_account(self, our_address: str, owned_account: "AccountInfo"):
        self.owned_accounts[our_address] = owned_account
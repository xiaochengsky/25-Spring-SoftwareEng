from enum import Enum
from TxDefi.Data.Amount import Amount
from TxDefi.Data.TransactionInfo import LiquidityPoolData, ParsedTransaction
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.Utilities.DEX.RugCheckerApi import RugCheckerApi
from TxDefi.Utilities.RateLimiter import RateLimiter

class Risk(Enum):
    NONE = 0
    LOW = 1
    MED = 2
    HIGH = 3

class RiskAssessor(RateLimiter):
    min_sol_liquidity = Amount.sol_ui(5)

    def __init__(self, solana_rpc_api: SolanaRpcApi):
        RateLimiter.__init__(self, 10)
        self.solana_rpc_api = solana_rpc_api
        self.rug_checker = RugCheckerApi()

    def liquidity_check(self, data: LiquidityPoolData, transaction: ParsedTransaction = None)->Risk:
        risk_rank = 0 #Rank 1-3 Low, 4-6 Med, 7+ High
        if data.pc_amount < self.min_sol_liquidity.to_scaled():
            print(f"TokenAccountsMonitor: pc sol amount {data.pc_amount} too low. Tx: {data.tx_signature}")
            risk_rank += 1

        if not transaction and len(data.lp_mint_address) > 0:
            top_accounts_value = self.solana_rpc_api.get_top_owners_total_holding(data.lp_mint_address, 100, None, False)
            
            if top_accounts_value > 0:
                risk_rank += 1

                #TODO put in a more sophistacated check; could use rugcheck api
                
        if risk_rank == 0:
            return Risk.NONE
        elif risk_rank >= 1 and risk_rank <=3:
            return Risk.LOW
        elif risk_rank >= 4 and risk_rank <= 6:
            return Risk.MED
        else:
            return Risk.HIGH

    def get_rug_check_info(self, token_address: str):
        if self.acquire_sem():
            return self.rug_checker.get_token_report(token_address)
    
    def calculate_lp_burned_percent(self, lp_token_address: str, token_supply: Amount)->float:
        top_accounts_value = self.solana_rpc_api.get_top_owners_total_holding(lp_token_address, 100, None, False)

        ret_percent = (1-top_accounts_value/token_supply.to_scaled())*100

        return ret_percent
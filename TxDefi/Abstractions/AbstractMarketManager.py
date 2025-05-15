from abc import abstractmethod
import threading

from TxDefi.DataAccess.Blockchains.Solana.RiskAssessor import RiskAssessor
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.Data.Candlesticks import Candlestick
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *

class AbstractMarketManager(threading.Thread):
    def __init__(self, solana_rpc_api: SolanaRpcApi, risk_assessor: RiskAssessor):
        threading.Thread.__init__(self, daemon=True)
        self.name = AbstractMarketManager.__name__
        self.solana_rpc_api = solana_rpc_api
        self.cancel_token = threading.Event()
        self.token_account_infos : dict[str, dict[str, AccountInfo]] = {} #key=account address; inner key=token address
        self.risk_assessor = risk_assessor

    def get_token_account_info(self, account_address: str, token_address: str)->AccountInfo:
        token_accounts = self.token_account_infos.get(account_address)

        if token_accounts:
            return token_accounts.get(token_address)

    def get_tokens_held(self, account_address: str)->list[AccountInfo]:
        token_accounts = self.token_account_infos.get(account_address)
        
        if token_accounts:
            return list(token_accounts.values())
        
    def get_risk_assessor(self)->RiskAssessor:
        return self.risk_assessor
    
    def monitor_token_accounts_state(self, account_address: str):
        if account_address not in self.token_account_infos:
            self.token_account_infos[account_address] = None
            self.update_token_accounts()
        
    @abstractmethod
    def run(self):
        pass
    
    def get_solana_rpc_api(self):
        return self.solana_rpc_api
    
    @abstractmethod
    def get_price(self, token_address: str)->Amount:
        pass
           
    @abstractmethod
    def get_token_info(self, token_address: str, monitor_token = True)->TokenInfo:
        pass
    
    @abstractmethod
    def get_candlesticks(self, token_address: str, interval: int)->list[Candlestick]:
        pass

    @abstractmethod
    def get_estimated_tokens(self, token_address: str, sol_amount: Amount)->Amount:
        pass

    @abstractmethod
    def get_estimated_price(self, token_address: str, token_quantity: Amount)->Amount:
        pass
    
    @abstractmethod
    def monitor_token(self, token_address: str, track_candles: bool)->TokenInfo:
        pass
    
    @abstractmethod
    def stop_monitoring_token(self, token_address: str):
        pass

    @abstractmethod
    def get_associated_token_account(self, owner_address: str, token_address: str)->str:
       pass

    @abstractmethod
    def get_extended_metadata(self, token_address)->ExtendedMetadata:
        pass

    @abstractmethod
    def get_status(self, token_address)->str:
        pass
    
    @abstractmethod
    def get_token_value(self, token_address: str, denomination: Denomination)->TokenValue:
        pass

    @abstractmethod
    def get_solana_price(self)->Amount:
        pass

    @abstractmethod
    def get_stats_tracker(self, token_address: str): #TODO
        pass

    @abstractmethod
    def toggle_new_mints(self):
        pass

    @abstractmethod
    def update_token_accounts(self):
        self

    @abstractmethod
    def stop(self):
        pass
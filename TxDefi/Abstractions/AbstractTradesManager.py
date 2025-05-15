from abc import abstractmethod
from typing import TypeVar, Generic
from TxDefi.Data.Amount import Amount
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
from TxDefi.Managers.WalletTracker import WalletTracker
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi

T = TypeVar("T", bound=ExecutableOrder)  # Generic type for Order subclasses

class AbstractTradesManager(Generic[T]):
    def __init__(self, solana_rpc_api: SolanaRpcApi, market_manager: AbstractMarketManager,  wallet_tracker: WalletTracker, 
                 default_trade_settings: SwapOrderSettings, default_wallet_settings: SignerWalletSettings):
        self.market_manager = market_manager   
        self.wallet_tracker = wallet_tracker
        self.solana_rpc_api = solana_rpc_api
        self.default_trade_settings = default_trade_settings
        self.default_wallet_settings = default_wallet_settings
    
    def get_wallet_tracker(self):
        return self.wallet_tracker
    
    def get_market_manager(self)->AbstractMarketManager:
        return self.market_manager
    
    def get_default_trade_settings(self)->SwapOrderSettings:
        return self.default_trade_settings
    
    def get_default_wallet_settings(self)->SignerWalletSettings:
        return self.default_wallet_settings
    
    def get_token_account_balance(self, token_address: str, owner_address: str):
        token_info = self.market_manager.get_token_info(token_address, False)

        if token_info:
            return self.solana_rpc_api.get_token_account_balance2(token_address, owner_address, token_info.metadata.token_program_address)

    def get_solana_rpc(self):
        return self.solana_rpc_api
    
    @abstractmethod
    def run_strategy_from_settings(self, strategy_settings: dict[str, any]):
        pass
    
    @abstractmethod
    def run_strategies(self, strategies_dir: str):
        pass

    @abstractmethod
    def execute(self, order: T, max_tries: int)->list[str]:
        pass

    @abstractmethod
    def get_sol_balance(self)->Amount:
        pass

    @abstractmethod
    def get_total_profit(self)->Amount:
        pass

    @abstractmethod
    def get_total_loss(self)->Amount:
        pass

    @abstractmethod
    def get_unrealized_sol(self)->Amount:
        pass

    @abstractmethod
    def sell_all(self):
        pass

    @abstractmethod
    def sweep(self):
        pass

    @abstractmethod
    def hold(self):
        pass
    
    @abstractmethod
    def toggle_auto_trade(self, id: str):
        pass
    
    #Pause/Unpause all trades
    @abstractmethod
    def toggle_auto_trades(self):
        pass
    
    @abstractmethod
    def get_status(self, mint_address: str)->str:
        pass
    
    @abstractmethod
    def get_pnl(self, mint_address: str)->ProfitLoss:
        pass

    @abstractmethod
    def wait_for_trade_info(self, tx_signature: str, timeout=30)->TradeInfo:
        pass

    @abstractmethod
    def get_exchange(self, token_address: str, amount_in: Amount, is_buy)->Amount:
        pass

    @abstractmethod
    def get_trade_info(self, tx_signature: str)->TradeInfo:
        pass

    @abstractmethod
    def get_swap_info(self, tx_signature: str, target_pubkey: str, maxtries: int)->list[SwapTransactionInfo]:
        pass

    @abstractmethod
    def get_swap_info_default_payer(self, tx_signature: str, maxtries: int)->list[SwapTransactionInfo]:
        pass
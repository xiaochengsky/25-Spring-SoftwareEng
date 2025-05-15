import time
import queue
import threading
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.DataAccess.Blockchains.Solana import RiskAssessor
from TxDefi.Engines.TokenAccountsMonitor import TokenAccountsMonitor
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import *
from TxDefi.DataAccess.Decoders.PumpDataDecoder import *
from TxDefi.Data.Candlesticks import *
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
import TxDefi.Utilities.FinanceUtil as finance_util
import TxDefi.Utilities.LoggerUtil as logger_util

#Manage Tokem Market Activities
class MarketManager(AbstractMarketManager):
    update_interval = 10
    supply_temp_value = Amount.tokens_ui(1e9, 6)
    def __init__(self, solana_rpc_api: SolanaRpcApi, accounts_monitor: TokenAccountsMonitor, risk_assessor: RiskAssessor):
        AbstractMarketManager.__init__(self, solana_rpc_api, risk_assessor)
        self.default_chart_intervals = [1, 60] #Keep 1-second, 1-minute  candlesticks; adjust as required
        self.candlesticks : dict[str, Candlesticks]= {}
        self.lp_monitor = accounts_monitor
        self.tx_event_queue = queue.Queue()
        self.tokens_locks : dict[str, threading.Lock] = {}
              
        self.auto_monitor_launches = False
        self.solana_price = Amount.sol_ui(0)
  
    def run(self):
        threading.Thread(target=self.update_market_parameters, daemon=True).start()        

        #Start monitoring pump and ray feeds
        self.toggle_pool_monitor()

    #if monitor_token, state of this token will continue to be managed via socket updates for efficiency      
    def get_token_info(self, token_address: str, monitor_token = True)->TokenInfo:
        if monitor_token and not self.lp_monitor.is_monitoring_token_info(token_address):
            ret_val = self.monitor_token(token_address)
        else:
            ret_val = self.lp_monitor.get_token_info(token_address)

        return ret_val
    
    def get_candlesticks(self, token_address: str, interval: int)->list[Candlestick]:
        if token_address in self.candlesticks:
            return self.candlesticks[token_address].get_candlestick_builder(interval).get_all()
       
    def get_price(self, token_address: str)->Amount:
        #Retrieve for lp monitors if available
        token_info = self.lp_monitor.get_token_info(token_address)

        if token_info:
            return token_info.get_price()
    
    def get_estimated_tokens(self, token_address: str, sol_amount: Amount)->Amount:
        token_info = self.get_token_info(token_address) #FIXME decimals not populated!
        tokens_amount = finance_util.estimate_exchange(token_info.sol_vault_amount.to_ui(), token_info.token_vault_amount.to_ui(), sol_amount.to_ui())

        return Amount.tokens_ui(tokens_amount, token_info.token_vault_amount.decimals)

    def get_estimated_price(self, token_address: str, token_quantity: Amount)->Amount:
        token_info = self.get_token_info(token_address)
        sol_amount = finance_util.estimate_exchange(token_info.token_vault_amount.to_ui(), token_info.sol_vault_amount.to_ui(), token_quantity.to_ui())

        return Amount.sol_ui(sol_amount)
    
    def get_swap_info(self, tx_signature: str, target_pubkey: str, maxtries = 30)->list[SwapTransactionInfo]:
        transaction = self.solana_rpc_api.get_transaction(tx_signature, maxtries)

        if transaction:
            return self.solana_rpc_api.parse_swap_transactions(target_pubkey, transaction)

    def get_associated_token_account(self, owner_address: str, token_address: str)->str:
        token_info = self.get_token_info(token_address, False)
        token_program_address : str = None

        if token_info:
            if len(token_info.metadata.token_program_address) > 0:
                token_program_address = token_info.metadata.token_program_address #TODO check if we even need to do this anymore
            else:
                token_metadata = self.get_extended_metadata(token_address)

                if token_metadata:
                    token_program_address = token_metadata.token_program_address

        if token_program_address:
            return self.solana_rpc_api.get_associated_token_account_address(owner_address, token_address, token_program_address)
        
    def monitor_token(self, token_address: str, track_candles = False)->TokenInfo:
        if track_candles and token_address not in self.candlesticks:
            self.candlesticks[token_address] = Candlesticks(intervals=self.default_chart_intervals)

        return self.lp_monitor.monitor_token(token_address)

    def stop_monitoring_token(self, token_address: str):
        if token_address in self.candlesticks:
            self.candlesticks.pop(token_address)

        self.lp_monitor.stop_monitoring_token(token_address)
    
    def get_extended_metadata(self, token_address)->ExtendedMetadata:
        return self.lp_monitor.get_complete_metadata(token_address)
            
    def toggle_new_mints(self):
         self.lp_monitor.toggle_new_mints()

    def toggle_pool_monitor(self):
        if self.auto_monitor_launches:
            self.lp_monitor.stop_monitoring()                  
        else:
            self.lp_monitor.start_monitoring()

        self.auto_monitor_launches = not self.auto_monitor_launches

    def _handle_token_update(self, arg1):
        if isinstance(arg1, str): #price update
            if arg1 in self.candlesticks:
                new_price = self.get_price(arg1).to_ui()

                self.candlesticks[arg1].update(datetime.now, new_price)
                #new_price_string = f"{new_price:.20f}"
                #print(arg1 + " Price: " + new_price_string)      

    def get_token_value(self, token_address: str, denomination: Denomination)->TokenValue:
        token_info = self.get_token_info(token_address, False)
        token_metadata = self.lp_monitor.get_complete_metadata(token_address)

        if token_info:
            if token_metadata and token_metadata.supply:
                total_supply = token_metadata.supply
            else:
                total_supply = self.solana_rpc_api.get_token_supply_Amount(token_info.token_address)

                if not total_supply:
                    total_supply = self.supply_temp_value #Use a temp value; This is just for display purposes

            token_price = token_info.get_price()

            if token_price:               
                ret_price = token_price
                market_cap_sol = token_price.to_ui()*total_supply.to_ui()

                if denomination == Denomination.USD:
                    solana_price = self.get_solana_price().to_ui()
                    usd_price = token_price.to_ui()*solana_price
                    ret_price = Amount.tokens_ui(usd_price, 0)
                    ret_market_cap = Amount.tokens_ui(market_cap_sol*solana_price, 0)
                else:
                    ret_market_cap = Amount.sol_ui(market_cap_sol)                         
        
                return TokenValue(token_address, ret_price, ret_market_cap)

    def update_token_accounts(self):
        for account_address in list(self.token_account_infos.keys()):
            token_account_infos = self.solana_rpc_api.get_token_accounts_by_owner(account_address)
            refreshed_accounts : dict[str, AccountInfo] = {}

            for token_account_info in token_account_infos:
                refreshed_accounts[token_account_info.mint_address]= token_account_info

            self.token_account_infos[account_address] = refreshed_accounts

    def get_status(self, token_address: str)->str:
        token_info = self.get_token_info(token_address)

        if token_info:
            if token_info.phase == TokenPhase.BONDING_IN_PROGRESS:
                return "Bonding Initiated - Don't Buy"
            else:
                token_value = self.get_token_value(token_address, Denomination.USD)

                if token_value:
                    market_cap = round(token_value.market_cap.to_ui(), 2)
                    #volumeObj = statsTracker.get_total_volume(60) #1 minute volume   
            
                    return f"MCAP: ${TokenValue.string_format(market_cap)}" #{volumeObj.to_string()}" #TODO                    
            
    def get_stats_tracker(self, token_address: str): #TODO
        pass

    def get_solana_price(self)->Amount:
        return self.solana_price
        
    def update_market_parameters(self):
        while not self.cancel_token.is_set():
            self.update_token_accounts()
            new_sol_price = solana_utilites.get_solana_price() #Add more robustness or switches if server provider goes down
            
            if new_sol_price:
                self.solana_price.set_amount2(new_sol_price, Value_Type.UI)

            time.sleep(self.update_interval)

    def stop(self):
        self.cancel_token.set()
        self.tx_event_queue.put(None)
        self.lp_monitor.stop()
    
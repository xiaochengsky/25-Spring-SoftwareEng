from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TransactionInfo import AccountInfo
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.DataAccess.Decoders.TransactionsDecoder import TransactionsDecoder
from TxDefi.Abstractions.AbstractSubscriber import AbstractSubscriber
from TxDefi.Data.TransactionInfo import SwapTransactionInfo
import threading

class CopyTrade:
    def __init__(self, our_balance : AccountInfo, their_balance : AccountInfo):
        self.our_account = our_balance
        self.their_account = their_balance

#Copy Trade Strategy. Buy when payer buys on your amount. Sell a percentage of tokens at the same % the payer sells at
class CopyTradeStrategy(AbstractTradingStrategy[AccountInfo], AbstractSubscriber[AccountInfo]):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [], settings)
        self.transaction_decoder = TransactionsDecoder()
        self.solana_rpc = self.trades_manager.get_solana_rpc()
        self.trade_lock = threading.Lock()

        for account in self.subbed_accounts:
            self.init_copy_trades(account)

        self.our_address = self.wallet_settings.get_default_signer().get_account_address()
        
    def init_copy_trades(self, account_address: str):
        self.trades_manager.get_wallet_tracker().subscribe_to_wallet(account_address, self)
        self.subbed_accounts[account_address] = AccountInfo(account_address, Amount.sol_ui(0))
       
    def make_trade(self, trade_type: TradeEventType, token_address: str, amount_in: Amount)->int:
        swap_settings = self.orig_swap_settings.clone()
        swap_settings.amount = amount_in
        self.swap_order = SwapOrder(trade_type, token_address, swap_settings, self.wallet_settings)

        tx_signatures = self.trades_manager.execute(self.swap_order, 3)

        if tx_signatures and len(tx_signatures) > 0:              
            print("Copy trade was successful! https://solscan.io/tx/" + tx_signatures[0])
            wallet_address = self.wallet_settings.get_default_signer().get_account_address()
            transaction_info_list = self.trades_manager.get_swap_info(tx_signatures[0], wallet_address, 30)
            transaction_info = transaction_info_list[0] if len(transaction_info_list) > 0 else None
          
            if transaction_info and transaction_info.token_balance_change != 0:
                return transaction_info.token_balance_change
        
    def update(self, data: AccountInfo):
        self.process_event(0, data)

    #process a subbed event
    def process_event(self, id: int, event: AccountInfo):
        if event.account_address in self.subbed_accounts:
            if self.trade_lock.acquire(False): #Only do a trade if we're not already doing one        
                #Get token transacted      
                
                json_data = self.trades_manager.get_solana_rpc().get_transaction_at_slot(event.last_slot, event.account_address)

                if json_data:
                    transactions = self.solana_rpc.parse_swap_transactions(event.account_address, json_data)

                    if len(transactions) > 0:
                        their_address = transactions[0].payer_address
                  
                        copy_trade_state: AccountInfo = self.subbed_accounts.get(their_address) #Check if we care about this address

                        if copy_trade_state:
                            their_token_account: AccountInfo = copy_trade_state.get_account(their_address)
                            our_token_account: AccountInfo = copy_trade_state.get_account(self.our_address)

                            for transaction in transactions:
                                #Update their balance
                                if their_token_account:
                                    their_token_account.balance.add_amount(transaction.token_balance_change, Value_Type.UI)

                                    #Update intial balance if the target is growing their position
                                    if their_token_account.balance.compare(their_token_account.initial_balance) > 0:
                                        their_token_account.initial_balance.set_amount(their_token_account.balance)
                                    initial_balance = their_token_account.initial_balance.to_ui() 

                                    if initial_balance != 0:      
                                        percent_change = their_token_account.balance.to_ui()/initial_balance-1
                                    else:
                                        percent_change = 0 #Not possible to get here, but just added for robustness              
                                else:
                                    percent_change = None

                                if transaction.token_balance_change > 0: #Target Bought Tokens
                                    should_buy = True if abs(transaction.sol_balance_change) > self.min_payer_buy.to_scaled() else False
                            
                                    if should_buy: #Target Bought Something
                                        if not their_token_account:                                    
                                            their_token_account = AccountInfo(transaction.token_address, Amount.tokens_ui(transaction.token_balance_change, transaction.token_decimals))    
                                            copy_trade_state.add_account(their_address, their_token_account)     

                                        if not our_token_account:
                                            our_token_account = AccountInfo(transaction.token_address, Amount.tokens_ui(0, transaction.token_decimals))   
                                            copy_trade_state.add_account(self.our_address, our_token_account)                                     
                                   
                                        amount_tokens_bought = self.make_trade(TradeEventType.BUY, transaction.token_address, self.orig_swap_settings.amount)
                                        #Could keep track of how many tokens we bought, but don't need that for a sell all later
                                        our_token_account.balance.add_amount(amount_tokens_bought, Value_Type.UI)
                                elif percent_change and percent_change < 0 and our_token_account: #Target Sold and we've copy traded                         
                                    if percent_change <= self.sell_all_percent:         
                                        #Sell the lot
                                        amount_sold_lamports = self.make_trade(TradeEventType.SELL, transaction.token_address, our_token_account.balance)
                                        our_token_account.balance.value = 0
                                        if amount_sold_lamports:
                                            self.state == StrategyState.COMPLETE
                            
            self.trade_lock.release()
                               
    def load_from_dict(self, strategy_settings: dict[str, any]):
        self.orig_swap_settings = SwapOrderSettings.load_from_dict(strategy_settings)
        self.wallet_settings = SignerWalletSettings.load_from_dict(strategy_settings)   
        self.min_payer_buy : float = strategy_settings.get('min_payer_buy', 1) #Min SOL to trigger copy trade
        self.sell_all_percent : float = strategy_settings.get('sell_trigger_percent', 1) #Percent at which to sell all; based on target's sold tokens          
        self.sell_all_percent = self.sell_all_percent/100
        
        self.subbed_accounts : dict[str, CopyTrade] = {} #key=their account address
        accounts : list[str] = strategy_settings.get('accounts', [])
        
        self.min_payer_buy = Amount.sol_ui(self.min_payer_buy)
  
        #Keep a record of our account balances to make smart copy trades
        our_account = AccountInfo(self.wallet_settings.get_default_signer().get_account_address(), Amount.sol_ui(0))
        for address in accounts:
            their_account = AccountInfo(address, Amount.sol_ui(0))
            self.subbed_accounts[address] = CopyTrade(our_account, their_account)

    def load_from_obj(self, obj: object): 
        pass
    
    @classmethod
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"CopyTradeStrategy":
        return CopyTradeStrategy(trades_manager, settings)
        

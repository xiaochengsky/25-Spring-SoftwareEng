from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.TransactionInfo import SwapTransactionInfo
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Strategies.Signals.TokenDipSignalGenerator import TokenDipSignalGenerator
import TxDefi.Data.Globals as globals

class BuyDipStrategy(AbstractTradingStrategy):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any]):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_token_update_event], settings)
    
    def process_event(self, id: int, event: any):
        if event == self.initial_order.token_address:
            trigger_state = self.token_dip_signal_generator.update()

            if trigger_state == SignalState.TRIGGERED:
                self.state = StrategyState.COMPLETE  
                tx_signature = self.trades_manager.execute(self.initial_order, max_tries = 3)

                if tx_signature:
                    #Setup a limit order with a stop loss
                    transaction_info_list : list[SwapTransactionInfo] = self.trades_manager.get_swap_info(tx_signature, self.initial_order.get_wallet_settings().get_default_signer().get_account_address())
                    transaction_info = transaction_info_list[0] if len(transaction_info_list) > 0  else None
                    
                    if transaction_info and transaction_info.token_balance_change > 0:
                        temp_calc = abs(transaction_info.sol_diff/transaction_info.token_balance_change)   
                        base_token_price = Amount.sol_scaled(temp_calc)
                        tokens_bought = Amount.tokens_ui(transaction_info.token_balance_change, transaction_info.token_decimals)
                        new_swap_settings = SwapOrderSettings(tokens_bought, self.initial_order.swap_settings.slippage,
                                                    self.initial_order.swap_settings.priority_fee)
             
                        sell_order = OrderWithLimitsStops(self.initial_order.token_address, base_token_price, TradeEventType.SELL,
                                                           new_swap_settings, False, self.initial_order.wallet_settings)
                        
                        for option in self.pnl_options:
                            sell_order.add_pnl_option(option)
                    
                        #Start a limit and stop loss order
                        self.trades_manager.execute(sell_order, max_tries = 3)
                else:
                    print("Issue with executing the trade!") #TODO future feature: notify user

                self.stop()

    def load_from_dict(self, strategy_settings: dict[str, any]):
        self.pnl_options: list[PnlOption] = []                       
        limit_orders = strategy_settings.get('limit_orders')
        stop_loss_orders = strategy_settings.get('stop_loss_orders')

        swap_settings = SwapOrderSettings.load_from_dict(strategy_settings)
        wallet_settings = SignerWalletSettings.load_from_dict(strategy_settings)
        token_address = strategy_settings.get("token_address")

        if swap_settings:
            
            if limit_orders:
                for order in limit_orders:
                    self.pnl_options.append(PnlOption.from_dict(order))

            if stop_loss_orders:
                for order in stop_loss_orders:
                    self.pnl_options.append(PnlOption.from_dict(order))

            trigger_drop_percent = Amount.percent_ui(strategy_settings.get('trigger_drop_percent'))
            chart_interval = strategy_settings.get('chart_interval')
            market_maager = self.trades_manager.get_market_manager()
            self.token_dip_signal_generator = TokenDipSignalGenerator(token_address, market_maager, 
                                                                            chart_interval, trigger_drop_percent)
            self.initial_order = SwapOrder(TradeEventType.BUY, token_address, swap_settings, wallet_settings)
            #Make sure we're monitoring this token
            market_maager.monitor_token(token_address, True)

    def load_from_obj(self, obj: object): 
        pass
    
    @classmethod
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"BuyDipStrategy":
        return BuyDipStrategy(trades_manager, settings)
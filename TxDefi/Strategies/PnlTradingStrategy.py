import threading
from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
import TxDefi.Data.Globals as globals

class PnlTradingStrategy(AbstractTradingStrategy):
    def __init__(self, trades_manager: AbstractTradesManager, settings: dict[str, any] = None):
        AbstractTradingStrategy.__init__(self, trades_manager, [globals.topic_token_update_event], settings)
        self.state = StrategyState.PENDING
        self.last_price : Amount = None
        self.event_process_lock = threading.Lock()
        self.unprocessed_event_counter = 0

    def run(self):          
        if self.initial_order.order_type == TradeEventType.BUY:
            success = False
            signature = ""
            new_order = self.initial_order.get_swap_order()
            tx_signatures = self.trades_manager.execute(new_order, max_tries = 3)
   
            if tx_signatures and len(tx_signatures) > 0:
                signature = tx_signatures[0]
                trade_info = self.trades_manager.wait_for_trade_info(signature)

                if trade_info:
                    success = True
                    #Initialize to actual amount of tokens bought (Base token price is based on the price before purchase; set desired profit percents higher to account for this)
                    self.current_tokens_amount = trade_info.amount_out

            if not success:                  
                print("PnlTradingStrategy: Could not confirm tx " + signature + ". Cancelling this order. Retry again.")
                return
        
        self.recalculate_target_prices(self.initial_order.base_token_price)
        #Make sure we're monitoring this token
        self.trades_manager.get_market_manager().monitor_token(self.initial_order.token_address)

        #Continue on with our normally scheduled programming
        super().run()

    def load_from_dict(self, strategy_settings: dict[str, any]):
        order = OrderWithLimitsStops.load_from_dict(strategy_settings)

        self.load_from_obj(order)

    def load_from_obj(self, order: OrderWithLimitsStops):
        self.initial_order = order

        self.default_signer = order.wallet_settings.get_default_signer() 
        self.swap_settings = order.swap_settings      
        self.current_tokens_amount = order.swap_settings.amount.clone()
        self.is_trailing = self.initial_order.is_trailing

    def recalculate_target_prices(self, base_token_price: Amount):
        self.limit_order_triggers : dict[float, TriggerPrice] = {}
        self.stop_loss_triggers : dict[float, TriggerPrice] = {}
        
        #Uses max slippage in order to sell immediately
        for limit_order in self.initial_order.limits:            
            trigger_price = self.get_trigger_price(base_token_price, self.current_tokens_amount, limit_order.trigger_at_percent,
                                                                                     limit_order.allocation_percent)
            self.limit_order_triggers[trigger_price.target_price.to_ui()] = trigger_price

            print(f"Limit Price: {trigger_price.target_price.to_ui()}")

        for stop_loss_order in self.initial_order.stop_losses:
            trigger_price = self.get_trigger_price(base_token_price, self.current_tokens_amount, stop_loss_order.trigger_at_percent,
                                                                                     stop_loss_order.allocation_percent)
            self.stop_loss_triggers[trigger_price.target_price.to_ui()] = trigger_price
            print(f"Stop Price: {trigger_price.target_price.to_ui()}")

        self.limit_order_keys = sorted(self.limit_order_triggers)
        self.stop_loss_order_keys = sorted(self.stop_loss_triggers, reverse=True)

    def _get_triggered_sell_amount(self, price: Amount)->Amount:
        if self.is_trailing and self.last_price and price.compare(self.last_price) > 0:
            self.recalculate_target_prices(price) #Recalculate limit order prices if price goes up if trailing is set

        order_keys = None

        #print(f"trigger price goal " + str(self.limit_order_trigger.target_price.to_ui())) #DELETE

        met_price_keys = [x for x in self.limit_order_keys if x <= price.to_ui()]

        if len(met_price_keys) > 0: #Check if limit order triggered
            order_keys = self.limit_order_keys
            order_triggers = self.limit_order_triggers
        else: #Check if stop loss order triggered
            met_price_keys = [x for x in self.stop_loss_order_keys if x >= price.to_ui()]

            if len(met_price_keys) > 0:
                order_keys = self.stop_loss_order_keys
                order_triggers = self.stop_loss_triggers

        if order_keys:
            total_amount_ui = 0

            for key in met_price_keys:
                print(f"Price={price.to_ui()} Order Triggered")
                total_amount_ui += order_triggers[key].in_sell_amount.to_ui()
                order_keys.remove(key) #remove them from the list so we don't reprocess the same trigger again

            return Amount.tokens_ui(total_amount_ui, self.limit_order_triggers[key].in_sell_amount.decimals)  

    def process_event(self, id: int, event: any):
        if event == self.initial_order.token_address and self.event_process_lock.acquire(blocking=False):
            new_price = self.trades_manager.get_market_manager().get_price(self.initial_order.token_address)
            
            #Check Target PNL or Stop Loss hasn't been triggered
            sell_amount = self._get_triggered_sell_amount(new_price)

            if sell_amount:
                if sell_amount.compare(self.current_tokens_amount) > 0:
                    sell_amount = self.current_tokens_amount

                new_order = SwapOrder(TradeEventType.SELL, self.initial_order.token_address, 
                                      SwapOrderSettings(sell_amount, self.swap_settings.slippage, self.swap_settings.priority_fee),
                                      self.initial_order.wallet_settings)
  
                tx_signatures = self.trades_manager.execute(new_order, max_tries = 3)
                
                if tx_signatures:
                    self.current_tokens_amount.add_amount(-sell_amount.to_ui(), Value_Type.UI) #Assumes all tokens sold

                    if self.current_tokens_amount.value <= 0:
                        self.state = StrategyState.COMPLETE  
                        self.stop()
                        
            self.event_process_lock.release()
        else:
            self.unprocessed_event_counter += 1

    @classmethod
    def create(cls, trades_manager: AbstractTradesManager, settings: dict[str, any])->"PnlTradingStrategy":
        return PnlTradingStrategy(trades_manager, settings) 
    
    @staticmethod
    def get_trigger_price(base_token_price: Amount, tokens_owned: Amount, trigger_percent: Amount, allocation_percent: Amount)->TriggerPrice:
        pnl_percent = trigger_percent.to_ui()/100
        target_price = Amount.sol_ui(base_token_price.to_ui()*(1+pnl_percent))

        allocation_percent = allocation_percent.to_ui()/100            
        allocated_amount = tokens_owned.clone()  
        allocated_amount.set_amount2(tokens_owned.to_ui()*allocation_percent, Value_Type.UI)

        return  TriggerPrice(allocated_amount, target_price)   

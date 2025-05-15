import curses
import time
from TxDefi.TxDefiToolKit import TxDefiToolKit
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.DataAccess.Blockchains.Solana.SolPubKey import *
import TxDefi.Utilities.ParsingUtilities as util

#Are these the same on every windows machine?
KEY_UP = 450
KEY_DOWN = 456
ENTER = 10
ESCAPE = 27
MAX_NAME = "max"
slippage = Amount.percent_ui(5)
priority_fee = Amount.sol_ui(.0004)
default_profit_limit = PnlOption(trigger_at_percent = Amount.percent_ui(600), allocation_percent = Amount.percent_ui(100))
default_stop_loss = PnlOption(trigger_at_percent = Amount.percent_ui(-80), allocation_percent = Amount.percent_ui(100))

class MenuOptions(Enum):
    BUY = 'Buy'
    BUY_AUTO_SELL = 'Buy - Auto Sell Limit Order'
    SELL = "Sell"
    BUY_LIMIT_ORDER = "Buy Limit Order"
    SELL_LIMIT_ORDER = "Sell Limit Order"
    EXIT = "Exit"

#Simple CLI GUI For Creating Buy, Sell, and Limit Orders TODO Polish this
class Main_CLS_Screen:
    def __init__(self, stdscr, txdefitk: TxDefiToolKit):
        curses.curs_set(0)   
        self.stdscr = stdscr
        self.txdefitk = txdefitk
        self.market_manager = txdefitk.market_manager
        self.trades_manager = txdefitk.trades_manager
        self.main_options = [MenuOptions.BUY, MenuOptions.BUY_AUTO_SELL, MenuOptions.SELL,
                              MenuOptions.SELL_LIMIT_ORDER, MenuOptions.EXIT] #MenuOptions.BUY_LIMIT_ORDER TODO
        self.current_menu = self.main_options
        self.exit = False
        self.console_mode = False

        self.payer = self.trades_manager.get_default_wallet_settings().get_default_signer()
        self.wallet_settings = SignerWalletSettings(self.payer)
        self.wallet_settings.add_wallet(self.payer)
        self.update_balance()
   
    def update_balance(self):
        sol_balance = self.trades_manager.wallet_tracker.get_account_balance(self.payer.get_account_address())
        
        if sol_balance:
            self.payer_sol_balance = sol_balance
        
    def show(self):
        self.current_option = 0

        while not self.exit:
            if not self.console_mode:
                self.current_menu = self.main_options
                self.stdscr.refresh()
                self.stdscr.clear()

                # 检查窗口大小
                max_y, max_x = self.stdscr.getmaxyx()
                if max_y < len(self.main_options) + 2 or max_x < 20:
                    self.stdscr.addstr(0, 0, "Please resize your terminal window to be larger")
                    self.stdscr.refresh()
                    time.sleep(1)
                    continue

                self.stdscr.addstr(0, 0, f"SOL Balance: {self.payer_sol_balance.to_ui()}")
                # Display options
                for i, option in enumerate(self.main_options):
                    if i == self.current_option:
                        self.stdscr.addstr(i+1, 0, option.value, curses.A_REVERSE)  # Highlight current option
                    else:
                        self.stdscr.addstr(i+1, 0, option.value)

            if self._manage_key_press():                                 
                self.update_balance()

    def _prompt_amount(self, message: str, amount_units: Amount_Units, decimals = 0)->Amount:
        ret_val = None    

        user_input = self._get_user_input(message)

        if util.is_float(user_input):
            ret_val = Amount(Value_Type.UI, amount_units, float(user_input), decimals)
        
        return ret_val

    def _prompt_user_sell_amount(self, token_info: TokenInfo)->Amount:
        ret_val = None
        sell_percent = self._prompt_amount(f"Enter a sell quantity (% of balance): ", Amount_Units.PERCENT)
        balance = self.trades_manager.solana_rpc_api.get_token_account_balance2(token_info.token_address, self.payer.get_account_address(), token_info.metadata.token_program_address)
        
        if balance and sell_percent:
            token_amount = sell_percent.to_ui()/100*balance.to_ui()
            ret_val = Amount.tokens_ui(token_amount, token_info.token_vault_amount.decimals)
        
        return ret_val

    def _run_trade(self, token_info: TokenInfo, order_type: TradeEventType):
        amount = None

        if order_type == TradeEventType.BUY:
            amount = self._prompt_amount("Enter a buy amount (SOL): ", Amount_Units.SOL, solana_utilites.SOL_DECIMALS)
        else:
            amount = self._prompt_user_sell_amount(token_info)
        
        if amount:
            order = SwapOrder(order_type, token_info.token_address, 
                              SwapOrderSettings(amount, slippage, priority_fee), self.wallet_settings)
            curses.endwin()
            tx_signature = self.trades_manager.execute(order, max_tries = 3)
            curses.doupdate()

            if tx_signature and len(tx_signature):
                return tx_signature[0]

    def _run_limit_order_trade(self, token_address, base_token_price: Amount, token_amount):    
        #Create and execute limit order on the tokens we bought
        swap_settings = SwapOrderSettings(token_amount, slippage, priority_fee)
        order = OrderWithLimitsStops(token_address, base_token_price, TradeEventType.SELL, swap_settings, False, self.wallet_settings)
        order.add_pnl_option(default_profit_limit)
        #order.add_pnl_option(stop_loss)
        
        self.trades_manager.execute(order, max_tries = 3)
    
    def _print_message(self, message):
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, message)

    def _get_user_input(self, prompt: str):
        self.stdscr.clear()
        curses.echo()
        self.stdscr.addstr(0, 0, prompt)
        user_input = self.stdscr.getstr(0, len(prompt))  # Read the input
        curses.noecho()  # Disable echo after getting input

        return user_input.decode('utf-8')
    
    def _manage_key_press(self):
        key = self.stdscr.getch()
        enter_pressed = False

        # Handle key presses
        if key == KEY_UP and self.current_option > 0:
            self.current_option -= 1
        elif key == KEY_DOWN and self.current_option < len(self.current_menu) - 1:
            self.current_option += 1
        elif key == ESCAPE:
            if not self.console_mode:
                self.console_mode = True
                curses.endwin()
            else:
                self.console_mode = False
                curses.doupdate()
        elif not self.console_mode and key == ENTER:  # Enter key
            if self.current_menu[self.current_option] == MenuOptions.EXIT:
                self.exit = True
                self.txdefitk.shutdown()
                sys.exit()

            token_address = self._get_user_input("Enter a token address to trade: ")

            try:        
                token_info = self.market_manager.get_token_info(token_address)
                enter_pressed = True            
                tx_signature = None    

                if len(token_address) == 0 or not token_info:
                    return

                if self.current_menu[self.current_option] == MenuOptions.BUY or self.current_menu[self.current_option] == MenuOptions.BUY_AUTO_SELL:
                    tx_signature = self._run_trade(token_info, TradeEventType.BUY)
                elif self.current_menu[self.current_option] == MenuOptions.SELL:
                    tx_signature = self._run_trade(token_info, TradeEventType.SELL)          

                if self.current_menu[self.current_option] == MenuOptions.BUY_AUTO_SELL or self.current_menu[self.current_option] == MenuOptions.SELL_LIMIT_ORDER:
                    base_token_price = None
                    payer_token_amount = None
                    profit_limit = None
                    stop_loss = None
                    curses.endwin()
                    
                    if tx_signature:
                        #Optional, could estimate what we bought if time is critical; stay tuned for bonus material on this
                        start_time = time.time()
                        transaction_info_list = self.trades_manager.get_swap_info(tx_signature, self.payer.get_account_address(), 30)   
                        transaction_info = transaction_info_list[0] if len(transaction_info_list) > 0 else None
                        
                        if transaction_info and transaction_info.token_balance_change > 0:                
                                execution_time = time.time() - start_time
                                base_token_price = Amount.sol_scaled(abs(transaction_info.sol_balance_change/transaction_info.token_balance_change))
                                payer_token_amount = Amount.tokens_ui(transaction_info.token_balance_change, token_info.token_vault_amount.decimals)
                             
                                print(f"Execution time: {execution_time:.6f} seconds")

                                transaction_info.print_swap_info()
                        
                        profit_limit = default_profit_limit
                        #stop_loss = default_stop_loss
                    else: #Just a Limit Order                     
                        payer_token_amount = self._prompt_user_sell_amount(token_info)      
                        profit_enry = self._prompt_amount("Enter the profit limit (% of current market price): ", Amount_Units.PERCENT)
                        #stop_loss_entry = self._prompt_user("Enter the stop loss limit (-% of current market price): ")
                        token_allocation = self._prompt_amount("Enter tokens allocation (% of balance): ", Amount_Units.PERCENT)                 

                        if payer_token_amount and profit_enry and token_allocation:
                            profit_limit = PnlOption(trigger_at_percent = profit_enry, allocation_percent = token_allocation)
                            base_token_price = self.market_manager.get_price(token_info.token_address)

                    if base_token_price and (payer_token_amount and payer_token_amount.value > 0):
                        #Create and execute limit order on the tokens we bought       
                        swap_settings = SwapOrderSettings(payer_token_amount, slippage, priority_fee)             

                        order = OrderWithLimitsStops(token_address, base_token_price, TradeEventType.SELL, swap_settings, False, self.wallet_settings)
                        order.add_pnl_option(profit_limit)
                        
                        if stop_loss:
                            order.add_pnl_option(stop_loss)

                        self.trades_manager.execute(order, max_tries = 3)
                    else:
                        print("Limit Order Failed. No tokens available.")                              
                        time.sleep(2)
                    
                    curses.doupdate()
            except Exception as e:
                print("Error processing this request: " + str(e))

        return enter_pressed
        
def main(stdscr):
    executor = TxDefiToolKit()

    main_screen = Main_CLS_Screen(stdscr, executor)
    main_screen.show()

    executor.join()

curses.wrapper(main)

import webbrowser
import threading
import customtkinter as ctk
import tkinter as tk
from PIL import Image
from TxDefi.UI.Components.InfoWidget import InfoWidgetWithHeader, InfoWidgetRow
from TxDefi.UI.Components.AdvancedOrderWidget import AdvancedOrderWidget
from TxDefi.UI.Components.VolumeWidget import VolumeWidget
from TxDefi.Managers.MarketManager import *
from TxDefi.Managers.TradesManager import TradesManager
from TxDefi.Utilities.ResourceStorage import ResourceStorage
import TxDefi.Data.Globals as globals
import TxDefi.DataAccess.Blockchains.Solana.SolanaUtilities as solana_utilites

#TODO add in a wallet selector

def validate_float(value):
    # Allow empty input for deleting
    if value == "" or value == ".":
        return True
    try:
        float(value)
        return True
    except ValueError:
        return False
          
class TokenSidebarWidget(ctk.CTkFrame):
    def __init__(self, parent, market_manager: MarketManager, trade_manager: TradesManager):
        super().__init__(parent, bg_color=globals.darkBgColor, fg_color=globals.darkBgColor)
        # Register the validation function with Tkinter
        self.market_manager = market_manager
        self.trade_manager = trade_manager
        self.buyIncrements = [.1, .25, .5, 1, 2, 5] #TODO Make user configurable (low priority)
        self.sellPercentIncrements = [10, 20, 25, 50, 75, 100]
        self.volumeIntervals = [("1M",0,60), ("5M",0,60*5), ("1H",0,3600), ("6H",0,3600*6), ("24H",0,3600*24)] #Header,Default Value,Seconds Window
        self.is_buy_selected = True
        self.auto_checkbox_var = ctk.IntVar()
        self.volumeWidgets = {}
        self.currency_pairA = "SOL"
        self.currencyPairB = "NA"
        self.lastTradeAmountA = self.buyIncrements[0]
        self.lastTradeAmountB = 0 
        self.amountEntryVar = ctk.StringVar()
        self.amountEntryVar.trace_add("write", self.on_entry_amount_changed)
        self.metadata : ExtendedMetadata = None

        self.stored_ctk_images : ResourceStorage[ctk.CTkImage] = ResourceStorage(10000, 5000)
        self.ui_inited = False
        self.lock = threading.Lock()

    def get_image(self, image: Image)->ctk.CTkImage:
        ret_image = self.stored_ctk_images.get_resource(self.metadata.token_address)

        if not ret_image:
            ret_image = ctk.CTkImage(image, size=(80, 80))
            self.stored_ctk_images.add_resource(self.metadata.token_address, ret_image)

        return ret_image

    def _load_image(self, image: Image):
        ctk_image = self.get_image(image)
        
        if ctk_image:     
            self.token_image.configure(image=ctk_image)
            self.token_image.pack()
        else:            
            self.token_image.pack_forget()

    def set_display(self, token_address: str, image: ctk.CTkImage):
        if not self.ui_inited:
            self._init_ui() 
            self.ui_inited = True
        
        if self.lock.acquire(timeout=2):
            token_info = self.market_manager.get_token_info(token_address)
   
            if token_info:         
                self.metadata = token_info.metadata
              
                if image:
                    self._load_image(image)

                self.symbolLabel.configure(text=token_info.metadata.symbol)
                self.tradeCurrencyLabel.configure(text=self.currency_pairA)
                self.currencyPairB = token_info.metadata.symbol
                
                self.configure_entry_amount()
                self._show_buy_settings()
            else:
                print("No TokenInfo")
        else:
            print("TokenSidebarWidget: set_display deadlock") #FIXME Can't figure out why this is happening sometimes
        self.lock.release()
        self.advanced_widget.reset()
        self.update_stats()
       
    def open_blockchain_uri(self, event):
        webbrowser.open(globals.default_solscanner_account_uri + "/" + self.metadata.token_address)

    #Update stats of this mint instance
    def update_stats(self):
        with self.lock:
            try:
                if self.metadata:  
                    token_info = self.market_manager.get_token_info( self.metadata.token_address, False)
                    if token_info and token_info.phase != TokenPhase.BONDING_IN_PROGRESS:
                        token_value = self.market_manager.get_token_value(token_info.token_address, Denomination.USD)
                        
                        market_cap = round(token_value.market_cap.to_ui(), 2)
                        self.mcapWidget.set_info("$" + TokenValue.string_format(market_cap))

                        price_rounded = round(token_value.price.to_ui(), 7)
                        self.priceWidget.set_info("$" + str(price_rounded))                 

                        #TODO Add risk status and volume info features in next phase
                        #risk_assessor = self.market_manager.get_risk_assessor()
                        #rug_check_info = risk_assessor.get_rug_check_info(token_info.token_address) 

                        #Do something with this
                        #if rug_check_info:
                        #    print(str(rug_check_info) + "\n")
                        #self.update_exchange_text()
                        #self.update_volume_info()
            except Exception as e:
                print("TokenSidebarWidget: Issue updating stats " + str(e))

    def update_exchange_text(self):        
        token_metadata = self.metadata
        if token_metadata:  
            try:
                label_text = ''
                amount_string = self.amountEntry.get()                    
                amount = 0 if len(amount_string) == 0 else float(amount_string)
      
                if amount > 0:
                    if self.is_buy_selected:                    
                        max_exchange = self.trade_manager.get_exchange(token_metadata.token_address, Amount.sol_ui(amount), self.is_buy_selected)
                        label_text = max_exchange.to_string(4) + " " + token_metadata.symbol
                    else:
                        token_info = self.market_manager.get_token_info(token_metadata.token_address, False)

                        if token_info:
                            max_exchange = self.trade_manager.get_exchange(token_metadata.token_address, Amount.tokens_ui(amount, token_info.token_vault_amount.decimals), self.is_buy_selected)
                            label_text = max_exchange.to_string(7)  + " SOL"

                self.token_exchange_info_label.configure(text=label_text)
            except Exception:
                return False
        else:
            self.token_exchange_info_label.configure(text="Token hasn't bonded!")

    #Configure volume interval in minutes
    def update_volume_info(self):
        statsTracker = self.market_manager.get_stats_tracker(self.metadata.token_address)

        if statsTracker:
            selectedindex = self.volumeWidget.get_selected_index()
            seconds = self.volumeIntervals[selectedindex][2]
            
            volumeObj = statsTracker.get_total_volume(seconds)
            uniqueMakers = len(statsTracker.get_unique_traders(seconds))
            totalTrades = volumeObj.numBuys + volumeObj.numSells
            tradeVol = round(volumeObj.tradeVolume/solana_utilites.SOL_SCALE_FACTOR, 5)
            buyVol = round(volumeObj.buyVolume/solana_utilites.SOL_SCALE_FACTOR, 5)

            self.volumeWidget.configure_volume_info(totalTrades, tradeVol, uniqueMakers, volumeObj.numBuys, buyVol)
     
    #Configure entry amount
    def configure_entry_amount(self):
        if self.is_buy_selected:
            selected = self.solAmountIncFrame.get_selected_widget()
            newAmount = float(selected.get_info())
        else:
           selected = self.tokenAmountIncFrame.get_selected_widget()
           newPercent = float(selected.get_info())/100
           balance = self._get_actual_token_balance()
           newAmount = newPercent*balance

        self._set_trade_amount(newAmount)   

    def _set_trade_amount(self, tradeAmount: float):
        self.amountEntry.delete(0, tk.END)
        self.amountEntry.insert(0, str(tradeAmount))

    def _show_buy_settings(self):
        if not self.is_buy_selected: 
            self.is_buy_selected = True

            self.lastTradeAmountB = self.amountEntry.get()
            
            self.tokenAmountIncFrame.forget()         
            self.solAmountIncFrame.pack(side=ctk.TOP, fill=ctk.BOTH)
            self.sellSelector.configure(fg_color=globals.disabledColor)
            self.buySelector.configure(fg_color=globals.greenButtonColor)
            self.tradeCurrencyLabel.configure(text=self.currency_pairA)

            self._set_trade_amount(self.lastTradeAmountA)
    
    def _show_sell_settings(self):
        if self.is_buy_selected: 
            self.lastTradeAmountA = self.amountEntry.get()
            self.is_buy_selected = False        
            self.solAmountIncFrame.forget() 
            self.tokenAmountIncFrame.pack(side=ctk.TOP, fill=ctk.BOTH)
            self.buySelector.configure(fg_color=globals.disabledColor)
            self.sellSelector.configure(fg_color=globals.redButtonColor)
            self.tradeCurrencyLabel.configure(text=self.currencyPairB)    

            self._set_trade_amount(self.lastTradeAmountB)

    def _get_actual_token_balance(self):
        account_balance = self.trade_manager.get_default_payer_token_account_balance(self.metadata.token_address)

        if account_balance:
            balance = account_balance.to_ui()
        else:
            balance = 0

        return balance
    
    def execute_trade(self):
        entry_amount = float(self.amountEntryVar.get())
        executable_order = None

        if self.is_buy_selected:
            trade_type = TradeEventType.BUY
            amount_in = Amount.sol_ui(entry_amount)
        else:
            trade_type = TradeEventType.SELL
            amount_in = Amount.tokens_ui(entry_amount, self.metadata.token_decimals)

        swap_settings = self.trade_manager.default_trade_settings.clone()
        swap_settings.amount = amount_in

        if self.auto_checkbox_var.get() != 0:     
            limit_orders = self.advanced_widget.get_orders()

            if limit_orders:
                price = self.market_manager.get_price(self.metadata.token_address)
                is_trailing = self.advanced_widget.is_trailing_checked()
                executable_order = OrderWithLimitsStops(self.metadata.token_address, price, trade_type, swap_settings, is_trailing)

                for pnloption in limit_orders:
                    executable_order.add_pnl_option(pnloption)

            target_mcap = self.advanced_widget.get_target_mcap()

            if target_mcap and target_mcap.to_ui() > 0: #Make this a MarkeCap Order
                mcap_order = McapOrder(trade_type, self.metadata.token_address, swap_settings, target_mcap, None, executable_order)
                executable_order = mcap_order
        
        if not executable_order:
            executable_order = SwapOrder(trade_type, self.metadata.token_address, swap_settings)

        threading.Thread(target=self.trade_manager.execute, args=(executable_order, 3), daemon=True).start()

    def on_entry_amount_changed(self, *args):
        self.update_exchange_text()

    def _init_ui(self):
        #Symbol Info Row        
        symbolFrame = globals.get_default_frame(self)
        symbolFrame.pack(side=ctk.TOP, expand=True)#, anchor=ctk.CENTER)

        self.token_image = ctk.CTkLabel(symbolFrame, text="", bg_color=globals.darkBgColor, fg_color=globals.darkBgColor)
        self.token_image.pack(side=ctk.TOP, fill=ctk.X, expand=True)

        self.symbolLabel = ctk.CTkLabel(symbolFrame, text="NA", text_color="white", cursor="hand2", bg_color=globals.darkBgColor, fg_color=globals.darkBgColor)
        self.symbolLabel.pack(side=ctk.TOP, fill=ctk.X, expand=True)
                
        self.symbolLabel.bind("<Button-1>", self.open_blockchain_uri)
        
        #Price & Market Cap Row #If you're placing widgets in a frame don't use fill
        marketDataFrame = globals.get_default_frame(self)
        marketDataFrame.pack(side=ctk.TOP, anchor=ctk.CENTER)

        self.priceWidget = InfoWidgetWithHeader(marketDataFrame, "Price", "0", headerTextColor="white", infoTextColor="white", 
                                      bg=globals.darkBgColor, highlightColor=globals.greenButtonColor, width=100, height=60)      
        self.priceWidget.pack(side=ctk.LEFT)

        self.mcapWidget = InfoWidgetWithHeader(marketDataFrame, "MCAP", "0", headerTextColor="white", infoTextColor="white", 
                                      bg=globals.darkBgColor, highlightColor=globals.greenButtonColor, width=100, height=60)
        self.mcapWidget.pack(side=ctk.LEFT)

        #Trade Selector Frame
        tradeSelectorFrame = ctk.CTkFrame(self)   
        tradeSelectorFrame.pack(side=ctk.TOP, fill=ctk.X)
                
        self.buySelector = ctk.CTkButton(tradeSelectorFrame, text="Buy", text_color="black", hover=False, fg_color=globals.greenButtonColor, command=self._show_buy_settings, corner_radius=0)
        self.buySelector.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
        
        self.sellSelector = ctk.CTkButton(tradeSelectorFrame, text="Sell", text_color="white", hover=False, fg_color=globals.disabledColor, command=self._show_sell_settings, corner_radius=0)
        self.sellSelector.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

        #User Entry Row
        amountEntryFrame = ctk.CTkFrame(self)   
        amountEntryFrame.pack(side=ctk.TOP, anchor="w")

        validateEntryCommand = amountEntryFrame.register(validate_float)
        self.amountEntry = ctk.CTkEntry(amountEntryFrame, textvariable=self.amountEntryVar, validate="key", validatecommand=(validateEntryCommand, '%P'))
        self.amountEntry.pack(side=ctk.LEFT, pady=3)

        self.tradeCurrencyLabel = ctk.CTkLabel(amountEntryFrame, text="SOL", text_color="white")
        self.tradeCurrencyLabel.pack(side=ctk.LEFT, fill=ctk.X, padx=4)

        self.amountIncrementsFrame = ctk.CTkFrame(self) 
        self.amountIncrementsFrame.pack(side=ctk.TOP, fill=ctk.X)

        self.solAmountIncFrame = InfoWidgetRow(self.amountIncrementsFrame, self.buyIncrements, self.configure_entry_amount, globals.greenButtonColor, globals.darkBgColor,
                                                globals.darkHighlightColor, True)
        self.solAmountIncFrame.pack(side=ctk.TOP, fill=ctk.BOTH)
        
        self.tokenAmountIncFrame = InfoWidgetRow(self.amountIncrementsFrame, self.sellPercentIncrements, self.configure_entry_amount, globals.greenButtonColor, globals.darkBgColor,
                                                globals.darkHighlightColor, True)
        self.token_exchange_info_label = ctk.CTkLabel(self, text="NA", text_color="white")
        self.token_exchange_info_label.pack(side=ctk.TOP, anchor='w')

        self.tradeExecuteButton = ctk.CTkButton(self, text="Execute", text_color="black", fg_color="yellow", command=self.execute_trade)
        self.tradeExecuteButton.pack(side=ctk.TOP, fill=ctk.X, pady=5)

        checkbox = ctk.CTkCheckBox(self, text="Auto Trade", variable=self.auto_checkbox_var, command=self._on_click_auto)
        checkbox.pack(side=ctk.TOP, anchor='w')

        # Frame to hold order tp and sl entries
        self.advanced_frame = ctk.CTkFrame(self, height=100)
        self.advanced_frame.pack(side=ctk.TOP, anchor='nw')

        self.advanced_widget = AdvancedOrderWidget(self.advanced_frame)

        #Create Volume Row
        self.volumeWidget = VolumeWidget(self, self.volumeIntervals, self.update_volume_info)
        #self.volumeWidget.pack(side=ctk.TOP, fill=ctk.X)
        self.volumeWidget.bind("<Button-1>", self.update_volume_info)
                        
        self._set_trade_amount(self.lastTradeAmountA)

        self.configure_entry_amount()
        self._show_buy_settings()

    def _on_click_auto(self):
        if self.auto_checkbox_var.get() != 0:
            self.advanced_widget.pack()#fill=ctk.X, expand=True)
        else:
            self.advanced_widget.forget()
             
def main():
        root = ctk.CTk()
        root.geometry("1450x915")  
        ctk.set_appearance_mode("dark")
        tokenWidget = TokenSidebarWidget(root, None, .15)
        tokenWidget.pack(side=ctk.TOP, fill=ctk.BOTH, anchor = ctk.CENTER)
        tokenWidget._init_ui()
        root.mainloop()

if __name__ == "__main__":
    main()

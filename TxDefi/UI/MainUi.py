from pubsub import pub
import queue
import customtkinter as ctk
import tkinter as tk
import threading
from datetime import datetime
import concurrent.futures
import time
# from PIL import Image
import platform
from PIL import Image, ImageTk

from TxDefi.Engines.TokenInfoRetriever import TokenInfoRetriever
from TxDefi.UI.Components.LogsFrame import LogsFrame
from TxDefi.UI.Components.WalletTable import WalletTable
from TxDefi.UI.Components.ThreadRunner import ThreadRunner
from TxDefi.UI.Components.AllPurposeTable import AllPurposeTable
from TxDefi.UI.Components.TokenSidebarWidget import TokenSidebarWidget
from TxDefi.TxDefiToolKit import TxDefiToolKit
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketEnums import *
from TxDefi.UI.Components.RowWidget import *
from TxDefi.UI.Components.ConfettiAnimator import ConfettiAnimator
from TxDefi.Utilities.SoundUtils import SoundUtils, SoundType
from TxDefi.Utilities.ResourceStorage import ResourceStorage
import TxDefi.Utilities.LoggerUtil as logger_util
import TxDefi.Data.Globals as globals
import TxDefi.UI.Components.GuiHelperFunctions as gui_functions
from TxDefi.UI.Components.AIAgentWidget import AIAgentWidget

marketDataKey = 'market_data'
tradeDataKey = 'trade_data'
load_file_path = "config/trade_state.json"

class MainUi(threading.Thread):
    max_tx_tries = 3
    processing_again_delay = 5

    def __init__(self, txdefitk: TxDefiToolKit, is_muted = True, *args, **kwargs):
        threading.Thread.__init__(self, daemon=True)
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.name = MainUi.__name__
        self.root.title("TradeMater")

        # self.root.iconbitmap(globals.txdefi_logo_path)
        # 修改这部分代码，根据操作系统设置图标
        try:
            if platform.system() == "Windows":
                self.root.iconbitmap(globals.txdefi_logo_path)
            elif platform.system() == "Linux":
                icon = Image.open(globals.txdefi_logo_path)
                photo = ImageTk.PhotoImage(icon)
                self.root.wm_iconphoto(True, photo)
            elif platform.system() == "Darwin":  # macOS
                pass
        except Exception as e:
            print(f"设置图标时出错（这不会影响程序运行）: {str(e)}")

        self.root.protocol("WM_DELETE_WINDOW", self.close)  # Handle close event
        self.root.geometry("1450x915")
        self.stored_images : ResourceStorage[Image] = ResourceStorage(10000, 5000) #Share image resources
        
        #self.state_saver_loader = StateSaverLoader(load_file_path)
        self.txdefitk = txdefitk
        self.trades_manager = txdefitk.trades_manager
        self.market_manager = txdefitk.market_manager
        self.wallet_tracker = self.trades_manager.get_wallet_tracker()
        self.trade_number = 0
        self.active_tokens = {}
        self.trade_save_states = dict()
        self.auto_bot_checkbox_var = ctk.IntVar()
        self.pause_feed_checkbox_var = ctk.IntVar()
        self.topFrame = ctk.CTkFrame(self.root)
        self.topFrame.pack(side=tk.TOP, fill=tk.X)  
        self.failed_events_queue = queue.Queue()
        self.main_events_queue = queue.Queue()
        self.ui_commands_queue = queue.Queue()
        self.active_pending_trades_table = None
        self.token_widget_map : dict[str, TradeWidget] = {} #key=token_address
        self.token_table_map : dict[str, AllPurposeTable] = {} #key=token_address
        self.ai_agent_widget = None
        self._init_menu()
        
        #Setup main frame
        self.mainFrame = ctk.CTkFrame(self.root)
        self.mainFrame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        #Set up right frame
        self.sideFrame = ctk.CTkFrame(self.root)
        self.sideFrame.pack(side=tk.RIGHT, fill=tk.Y)
        self.token_side_trade_widget = TokenSidebarWidget(self.sideFrame, self.market_manager, self.trades_manager)
        self.token_side_trade_widget.pack(side=tk.TOP, fill=tk.Y)
        
        self.centerFrame = ctk.CTkFrame(self.mainFrame)
        self.centerFrame.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

        self.bottomFrame = ctk.CTkFrame(self.mainFrame)        
        self.bottomFrame.pack(side=tk.TOP, fill=tk.BOTH)

        self.sound_utils = SoundUtils()
        self.sound_utils.muted = is_muted

        self.draw_canvas = tk.Canvas(self.sideFrame, bg="black", highlightthickness=0, width=100, height=250)
        self.draw_canvas.pack(fill=tk.X, expand=True, anchor="s")
        self.confetti_widget = ConfettiAnimator(self.sideFrame, self.draw_canvas, self.sound_utils, is_muted)
        self._init_trades_frames()
        self._init_bottom_row()

        #Set Default View
        self.curr_selected_view_id = TableType.PUMP_PENDING_VIEW                
        self._show_pending_trades_tables(self.new_pump_trades_table)

        #Bind so we can get clicked item
        self.new_pump_trades_table.bind("<Button-1>", lambda e: self._trades_table_clicked(e, self.new_pump_trades_table))
        self.new_bonded_trades_table.bind("<Button-1>", lambda e: self._trades_table_clicked(e, self.new_bonded_trades_table))
        self.active_trades_table.bind("<Button-1>", lambda e: self._trades_table_clicked(e, self.active_trades_table))
        self.watcher_table.bind("<Button-1>", lambda e: self._trades_table_clicked(e, self.watcher_table))
        self.user_wallet_table.bind("<Button-1>", lambda e: self._trades_table_clicked(e, self.user_wallet_table))
        self.trade_tables : dict[TableType, AllPurposeTable] = {}

        self.trade_tables[TableType.PUMP_PENDING_VIEW] = self.new_pump_trades_table    
        self.trade_tables[TableType.BONDED_PENDING_VIEW] = self.new_bonded_trades_table
        self.trade_tables[TableType.WATCHING_VIEW] = self.watcher_table
        self.trade_tables[TableType.WALLET_VIEW] = self.user_wallet_table
  
        self.updateStatsThread = ThreadRunner(2)
        self.updateStatsThread.add_callback("update_stats", self.update_stats)
       
        self.failed_events_thread = ThreadRunner(10)
        self.failed_events_thread.add_callback("process_failed_events", lambda: self._process_events(self.failed_events_queue, False)) 
        
        self.events_thread = ThreadRunner(1)
        self.events_thread.add_callback("process_events", lambda: self._process_events(self.main_events_queue, True)) 
        
        self.ui_commands_thread = ThreadRunner(1)
        self.ui_commands_thread.add_callback("process_ui_commands", lambda: self._process_ui_commands(self.ui_commands_queue)) 
        self.waiting = False
        #self.load()  
    
    def show_modal(self):
        self.start()
        self.root.mainloop()   
    
    def run(self):      
        pub.subscribe(topicName = globals.topic_ui_command, listener = self._handle_ui_command)
        pub.subscribe(topicName = globals.topic_trade_event, listener = self._handle_trade_event)        
        pub.subscribe(topicName = globals.topic_token_alerts, listener = self._update_events_queue)      

        self.updateStatsThread.start()
        self.events_thread.start()
        self.failed_events_thread.start() 
        self.ui_commands_thread.start()

    def _forget_children(self, frame: ctk.CTkFrame):
        for children in frame.winfo_children():
            children.pack_forget()
    
    def _trades_table_clicked(self, event, table: AllPurposeTable):
        table.on_click(event)
        selected_id = table.get_selected_id()
        resource = self.stored_images.get_resource(selected_id)
        
        if not resource:
            token_info = self.market_manager.get_token_info(selected_id, False)

            if token_info and len(token_info.metadata.image_uri) > 0:
                resource = self.add_image_resource(selected_id, token_info.metadata.image_uri)
                
        self.toggle_wait_cursor()
        self.token_side_trade_widget.set_display(selected_id, resource)
        self.toggle_wait_cursor()

    def _show_pending_trades_tables(self, table: AllPurposeTable):
        self._forget_children(self.centerFrame)
        
        self.active_pending_trades_table = table
        table.pack(side=tk.TOP, expand=True, fill=tk.BOTH)
        self.active_trades_table.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

    def _show_table(self, table: AllPurposeTable):
        self._forget_children(self.centerFrame)
        
        table.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

    def _init_menu(self):
        self.pump_trades_label = gui_functions.create_view_change_label(self.topFrame, self, "Pump", TableType.PUMP_PENDING_VIEW, textColor="white")
        self.pump_trades_label.pack(side=ctk.LEFT, padx=5, pady=5)

        self.bonded_trades_label = gui_functions.create_view_change_label(self.topFrame, self, "Bonded", TableType.BONDED_PENDING_VIEW)
        self.bonded_trades_label.pack(side=ctk.LEFT, padx=5, pady=5)

        self.watcherLabel = gui_functions.create_view_change_label(self.topFrame, self, "Watching", TableType.WATCHING_VIEW)
        self.watcherLabel.pack(side=ctk.LEFT, padx=5, pady=5)

        self.walletLabel = gui_functions.create_view_change_label(self.topFrame, self, "Wallet", TableType.WALLET_VIEW)
        self.walletLabel.pack(side=ctk.LEFT, padx=5, pady=5)
        
        self.completedLabel = gui_functions.create_view_change_label(self.topFrame, self, "Completed", TableType.COMPLETED_VIEW)
        self.completedLabel.pack(side=ctk.LEFT, padx=5, pady=5)

        config_button = gui_functions.create_icon_button(self.topFrame, globals.configuration_logo_path)
        config_button.pack(side=ctk.RIGHT, pady=5)
        #Add SOL Bar to mainframe     
        solStatusFrame = globals.get_default_frame(self.topFrame)
        solStatusFrame.pack(side=ctk.RIGHT, fill=ctk.X)#, padx=260)
     
        self.token_entry = ctk.CTkEntry(solStatusFrame, width=330)
        self.token_entry.pack(side=ctk.LEFT, padx = 0)

        self.tokenAddButton = ctk.CTkButton(solStatusFrame, text="Add", width=20, text_color="black", fg_color=globals.greenButtonColor, command=self.add_token)
        self.tokenAddButton.pack(side=ctk.LEFT, padx = 2)

        #TODO icons
        sol_button = gui_functions.create_icon_button(solStatusFrame, globals.sol_logo_path)
        sol_button.pack(side=ctk.LEFT, padx=5)
        self.userSolLabelValue = ctk.CTkLabel(solStatusFrame, text=" LOADING", font=globals.get_default_font(15, True), text_color="white")
        self.userSolLabelValue.pack(side=ctk.LEFT, padx = 5)

    def _init_trades_frames(self):     
        styleId1 = gui_functions.set_default_treeview_style(False) #Remove highlight on active trades
        styleId2 = gui_functions.set_default_treeview_style(False) #Keep highlight for completed trades

        pendingHeader = BuyTradeWidget.get_header()        
        self.new_pump_trades_table = AllPurposeTable(self.centerFrame, True, pendingHeader, 50, styleId1, cursor="hand2")

        pendingHeader = BuyTradeWidget.get_header()        
        self.new_bonded_trades_table = AllPurposeTable(self.centerFrame, True, pendingHeader, 50, styleId1, cursor="hand2")

        activeHeader = SellTradeWidget.get_header()   
        self.active_trades_table = AllPurposeTable(self.centerFrame, True, activeHeader, 50, styleId1, cursor="hand2")

        completedHeader = ("Timestamp", "Mint Address", "PnL %", "PnL")     
        self.completed_trades_table = AllPurposeTable(self.centerFrame, False, completedHeader, 1000, styleId2, cursor="hand2")

        #Add Watched Wallet Frame    
        self.watcher_table = AllPurposeTable(self.centerFrame, False, pendingHeader, 1000, styleId1, cursor="hand2")

        #Create User Wallet Frame
        self.user_wallet_table = WalletTable(self.centerFrame, True, 1000, styleId1, self.market_manager, self.trades_manager, cursor="hand2")

        self.user_wallet_table.update_table()

    def _init_bottom_row(self):
        bottom_button_frame = ctk.CTkFrame(self.bottomFrame)   
        bottom_button_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, padx=10)
        
        self.sellAllButton = ctk.CTkButton(bottom_button_frame, text="Panic Sell", text_color="white", fg_color=globals.redButtonColor, command=self.sell_all)
        self.sellAllButton.pack(fill=ctk.X, pady = 10)
        self.sweepButton = ctk.CTkButton(bottom_button_frame, text="Sweep", text_color="white", fg_color=globals.redButtonColor, command=self.sweep)
        self.sweepButton.pack(fill=ctk.X, pady = 10)
     
        # Create and place a auto bot checkbox
        strategies_settings_frame = globals.get_default_frame(bottom_button_frame)   
        strategies_settings_frame.pack(fill=ctk.X, pady = 5)
        checkbox = ctk.CTkCheckBox(strategies_settings_frame, text="Run Strategies", variable=self.auto_bot_checkbox_var, command=self._onclick_auto_trade)
        checkbox.pack(side=ctk.LEFT, pady=5)
              
        strategies_button = gui_functions.create_icon_button(strategies_settings_frame, globals.strategies_logo_path)
        strategies_button.pack(side=ctk.LEFT, pady=10)

        checkbox = ctk.CTkCheckBox(bottom_button_frame, text="Pause Feed", variable=self.pause_feed_checkbox_var, command=self._onclick_pause_feed)
        checkbox.pack(fill=ctk.X, pady = 5)

        self.logsFrame = LogsFrame(self.bottomFrame)
        self.logsFrame.pack(side=ctk.LEFT, pady = 10, fill=ctk.X, expand=True)
        
        # Add AI Agent widget
        self.ai_agent_widget = AIAgentWidget(self.bottomFrame)
        self.ai_agent_widget.pack(side=ctk.LEFT, pady = 10, fill=ctk.BOTH, expand=True)
        
        logger_util.init_logger(self.logsFrame.get_log_display())
    
    def _set_view_label(self, view_id: int, color: str):
        if view_id == TableType.PUMP_PENDING_VIEW:
            self.pump_trades_label.configure(text_color=color)
        elif view_id == TableType.BONDED_PENDING_VIEW:
           self.bonded_trades_label.configure(text_color=color)
        elif view_id == TableType.COMPLETED_VIEW:
            self.completedLabel.configure(text_color=color)
        elif view_id == TableType.WATCHING_VIEW:
            self.watcherLabel.configure(text_color=color)
        elif view_id == TableType.WALLET_VIEW:
            self.walletLabel.configure(text_color=color)

    def _change_view_frame(self, view_id: int):
        if view_id != self.curr_selected_view_id:
            self._set_view_label(self.curr_selected_view_id, "grey")

            self.curr_selected_view_id = view_id

            if view_id == TableType.PUMP_PENDING_VIEW:
                self._show_pending_trades_tables(self.new_pump_trades_table)
            elif view_id == TableType.BONDED_PENDING_VIEW:
                self._show_pending_trades_tables(self.new_bonded_trades_table)
            elif view_id == TableType.COMPLETED_VIEW:
                self._show_table(self.completed_trades_table)
            elif view_id == TableType.WATCHING_VIEW:
                self._show_table(self.watcher_table)
            elif view_id == TableType.WALLET_VIEW:
                self._show_table(self.user_wallet_table)

            self._set_view_label(view_id, "white")

    def sell_all(self):
        self.trades_manager.sell_all()
        #globals.send(topicName = globals.topic_ui_command, data = Command(UI_Command.SELL_ALL))

    def sweep(self):
        self.trades_manager.sweep()
        #globals.send(topicName = globals.topic_ui_command, data = Command(UI_Command.SWEEP))

    def add_token(self):
        #self.toggle_wait_cursor()
        mint_address = self.token_entry.get()     
           
        self.ui_commands_queue.put(LoadSideWidgetCommand(mint_address))
        self.main_events_queue.put(MarketAlert(mint_address, TradeEventType.NEW_MINT, SupportedPrograms.WATCHER_WALLET))
        #self.toggle_wait_cursor()

    #Reevaluate
  #def update_widgets(self, trackersList: list, widgetsList: list, gridFrame: ThumbnailGrid):
  #        for tracker in trackersList:            
  #           volumeInfo = tracker.get_total_volume(30)
  #           solValue = self.marketManager.get_sol_value(tracker.mint_address)
  #           widget = widgetsList[tracker.mint_address]
  #           widget.ranking = volumeInfo.tradeVolume
  #           widget.set_volume_label(volumeInfo.to_string())
  #           widget.set_sol_label(str(solValue) + " SOL")   

    #Update new mints frame
    def update_stats(self):        
        if self.trades_manager:        
            sol_balance = self.trades_manager.get_sol_balance()
        
            if sol_balance:
                sol_string = sol_balance.to_string(6) 
                profit_string = self.trades_manager.get_total_profit().to_string(6)
                #loss_string = self.trades_manager.get_total_loss().to_string(6)
                unrealized_string = self.trades_manager.get_unrealized_sol().to_string(6)
                
                sol_message = f"{sol_string} Profit {profit_string} Unrealized: {unrealized_string}"
            
                #Keep all table items updated
                keys = list(self.active_tokens.keys())

                for token_address in keys:
                    self.__update_table(token_address)

                self.userSolLabelValue.configure(text=sol_message)
     
                self.token_side_trade_widget.update_stats()
                                
                if self.curr_selected_view_id == TableType.WALLET_VIEW:     
                    self.user_wallet_table.update_table()      

    def _schedule_queue_event(self, event: any, queue: queue.Queue):
        queue.put(event)

    def _process_events(self, queue: queue.Queue, retry_if_failed: bool):
        while queue.qsize() > 0:
            event = queue.get()
            
            if not self._process_trade_alert(event) and retry_if_failed:
                print("MainUi: Processing failed: Retrying after " + str(event) + " " + event.token_address) 
                threading.Timer(self.processing_again_delay, self._schedule_queue_event, args=(event, self.failed_events_queue)).start()
        
    #Use if commands require modding the gui
    def _process_ui_commands(self, queue: queue.Queue[Command]):
        while queue.qsize() > 0:
            command = queue.get()

            if isinstance(command, DeleteCommand):
                self._delete_pending_trade(command.mint_address)
            elif isinstance(command, LoadSideWidgetCommand):
                token_info = self.market_manager.monitor_token(command.mint_address)

                if token_info:
                    image = self.add_image_resource(command.mint_address, token_info.metadata.image_uri)

                    self.token_side_trade_widget.set_display(command.mint_address, image)
                    logger_util.logger.info(f"Loaded {command.mint_address} successfully!")

    def _handle_ui_command(self, arg1: TradeCommand | LoadSideWidgetCommand):
        if arg1.command_type == UI_Command.DELETE: #Should only affect pending
            self.ui_commands_queue.put(arg1) #Need to handle the removal in UI thread
            self.market_manager.stop_monitoring_token(arg1.mint_address)
        elif arg1.command_type == UI_Command.BUY or arg1.command_type == UI_Command.SELL: 
            if arg1.command_type == UI_Command.BUY:
                order_type = TradeEventType.BUY
            else:
                order_type = TradeEventType.SELL
            order = SwapOrder(order_type, arg1.mint_address, arg1.amount_in, self.trades_manager.default_trade_settings)
            signatures = self.trades_manager.execute(order, self.max_tx_tries)

            if signatures:
                logger_util.logger.info("Tx Successful; signature: " + signatures[0])
            else:
                logger_util.logger.info("Tx Failed")                
        elif arg1.command_type == UI_Command.SELL_ALL:
            self.trades_manager.sell_all()
        elif arg1.command_type == UI_Command.SWEEP: #Sell all negative PNL trades
            self.trades_manager.sweep()
        elif arg1.command_type == UI_Command.HOLD:
            self.trades_manager.hold(arg1.mint_address)

    def add_image_resource(self, token_address: str, image_uri: str)->Image:
        if len(image_uri) > 0:
            image = gui_functions.retrieve_image(image_uri)

            if image:
                self.stored_images.add_resource(token_address, image)
            
            return image
    
    def _handle_trade_event(self, arg1: TradeInfo | list[TradeInfo]):
        if isinstance(arg1, list):
            for trade_info in arg1:
                self.main_events_queue.put(trade_info)
        else:
            self.main_events_queue.put(arg1)

    def toggle_wait_cursor(self):
        self.waiting = not self.waiting

        if self.waiting:
            self.root.config(cursor="watch")  # Change to busy cursor
        else:
            self.root.config(cursor="arrow")  # Reset cursor back to normal 

        self.root.update_idletasks()  # Force UI update

    def _onclick_pause_feed(self):
        if self.pause_feed_checkbox_var.get():
            self.market_manager.toggle_new_mints()

    def _onclick_auto_trade(self):
        self.trades_manager.toggle_auto_trades()

    def _delete_pending_trade(self, token_address: str):
        table = self.token_table_map.get(token_address)

        if table:
           table.delete_row(token_address)
           self.token_table_map.pop(token_address)
           self.token_widget_map.pop(token_address)

    #Process wallets we monitor
    def _process_wallet_trade(self, wallet_event : WalletEvent):
        retail_transaction = wallet_event.retailTransaction
        trader_alias = self.wallet_tracker.get_wallet_alias(retail_transaction.trader_address)
        
        if trader_alias:
            if retail_transaction.get_type() == TradeEventType.BUY:       
                logger_util.logger.info(trader_alias + " bought " + wallet_event.token_address)
            else:
                logger_util.logger.info(trader_alias + " sold " + wallet_event.token_address)  
            
            token_info = self.market_manager.get_token_info(wallet_event.token_address)
            
            if token_info:        
                tradeWidget = BuyTradeWidget(token_info.token_address, token_info.metadata, "0", TableType.WALLET_VIEW, True)
                self._load_image(token_info, self.user_wallet_table)
                self.watcher_table.insert_row(wallet_event.token_address, tradeWidget)
                self.sound_utils.play_sound(SoundType.ALERT)

    def get_table_type(self, supported_program: SupportedPrograms):
        if supported_program == SupportedPrograms.PUMPFUN:
            return TableType.PUMP_PENDING_VIEW
        elif supported_program == SupportedPrograms.WATCHER_WALLET:
            return TableType.WATCHING_VIEW
        else:
            return TableType.BONDED_PENDING_VIEW
        
    #Update our stats
    def _process_trade_alert(self, arg1: MarketAlert | TradeInfo):
        status = True

        if arg1.get_type() == TradeEventType.NEW_MINT or arg1.get_type() == TradeEventType.ADD_LIQUIDITY:
            status = self._process_new_token(arg1.token_address, self.get_table_type(arg1.get_program_type()))
        elif arg1.get_type() == TradeEventType.BUY or arg1.get_type() == TradeEventType.SELL:
            status = self._handle_trade(arg1)
        elif arg1.get_type() == TradeEventType.PNL:
            status = self._process_pnl(arg1)
        elif arg1.get_type() == TradeEventType.BONDING_COMPLETE:
            self._process_bonding_complete(arg1.token_address)
        elif arg1.get_type() == AlertReason.DEV_JEETED:
            pass #TODO Updata ui entry (show dev sold icon)
        elif isinstance(arg1, WalletEvent):
            self._process_wallet_trade(arg1)

        return status
        #elif isinstance(arg1, RetailTransaction):
        #    #Update tables
        #    self.__update_table(arg1.mint_address)
        #
            #if self.pendingTradesTable.has_id(arg1.mint_address):
            #    marketData = self.marketManager.fetch_token_market_data(arg1.mint_address)
        #
            #    if marketData:
            #        mcapSol = marketData.get_market_cap()
            #        mcapUsd = self.marketManager.get_solana_price()*mcapSol
            #       
            #        #if mcapUsd > 13000 and self.autoBotCheckboxVar.get(): #DELETE
            #        #    self.pendingTradesTable.delete_row(arg1.mint_address)
            #        #    self.tradeManager.start_trade(arg1.mint_address, 0, False)                       
            #        #else:                    

    #Process PNL Event
    def _process_pnl(self, arg1: ProfitLoss):
        token_info = self.market_manager.get_token_info(arg1.token_address) 
        success = False

        if token_info:
            pnl_percent = arg1.pnl_percent

            timestamp = datetime.now().timestamp()
            tags = []

            if pnl_percent.to_ui() < 0:
                tags.append(globals.highlight_red)
            else:
                tags.append(globals.highlight_green)

            pnl_log = (f"{timestamp},{arg1.token_address},{pnl_percent.to_string(2)},{arg1.token_quantity.to_string(2)},{arg1.cost_basis.to_string(6)},{self.trades_manager.get_sol_balance().to_string(6)},"
                      f"{self.trades_manager.get_unrealized_sol().to_string(6)}")
            logger_util.logger.info(pnl_log)

            click_uri = globals.default_solscanner_tx_uri +  "/" + arg1.tx_signature
            col0 = TextProperty(str(timestamp))
            col1 = ClickableProperty(lambda e: webbrowser.open(click_uri), arg1.token_address)
            col2 = TextProperty(f"{pnl_percent.to_string(2)}%")
            col3 = TextProperty(f"{arg1.pnl.to_string(7)} SOL")
            row_widget = ClickableRowWidget(token_info.token_address, [col0, col1, col2, col3])
            self.completed_trades_table.insert_row(str(self.trade_number), row_widget, tags)
            self.trade_number += 1
            success = True
            
            if arg1.is_complete and arg1.token_address in self.active_tokens:
                self.active_tokens.pop(arg1.token_address)
                self.active_trades_table.delete_row(arg1.token_address)
                #self._unsave_trade(arg1.mint_address)        
             
                #Resave File DELETE
                #self.stateSaverLoader.save_to_file(self.tradeStates)

        return success
    
    def _load_token_image(self, token_metadata: ExtendedMetadata, target_table: AllPurposeTable):
        success = False
        for _ in range(3):    
            if len(token_metadata.image_uri) == 0 and len(token_metadata.inner_metadata_uri) > 0:
                #Pull the image
                success = TokenInfoRetriever.fetch_and_fill_inner_metadata(token_metadata, token_metadata.inner_metadata_uri)
            else: #Either image info is available already or this token has no image
                success = True
                             
            if success and len(token_metadata.image_uri) > 0:
                image = self.add_image_resource(token_metadata.token_address, token_metadata.image_uri)     

                if image:       
                    target_table.load_image(token_metadata.token_address, image)
                    
                if token_metadata.socials.num_socials() > 0:
                    target_table.set_socials(token_metadata.token_address, token_metadata.socials.to_string())
                        
                return #Loaded the image and all so kick out of this loop
         
            time.sleep(5) #Try again every 5 second
        
        print("MainUI: Cannot display, failed to load metadata for " + token_metadata.token_address)
     
    def _process_new_token(self, token_address: str, table_type: TableType):
        if not token_address in self.active_tokens or table_type == TableType.WATCHING_VIEW:
            target_table = self.trade_tables.get(table_type)
            token_info = self.market_manager.get_token_info(token_address, False)

            if token_info:
                trade_widget = BuyTradeWidget(token_address, token_info.metadata, 'No Data', table_type, True)
                trade_widget.set_ranking(0)                        
                self.active_tokens[token_address] = token_address
                self._assign_widget(trade_widget, target_table)

        return True

    def _load_image(self, token_metadata: ExtendedMetadata, table: AllPurposeTable):
        threading.Thread(target=self._load_token_image, args=(token_metadata, table)).start()

    def _assign_widget(self, trade_row_widget: TradeWidget, table: AllPurposeTable):
        table.insert_row(trade_row_widget.token_address, trade_row_widget)   

        self.token_table_map[trade_row_widget.token_address] = table #FYI use a dict if multiple table listings are needed
        self.token_widget_map[trade_row_widget.token_address] = trade_row_widget
        self._load_image(trade_row_widget.metadata, table)

    def _process_bonding_complete(self, token_address: str):
        self.sound_utils.play_sound(SoundType.BONDING_COMPLETE)              
        widget = self.token_widget_map.get(token_address)

        if widget: #Must have been bonding
            wtable = self.token_table_map.get(token_address)
     
            if wtable:
                wtable.delete_row(token_address) 

            #Assign it to the new table
            widget.table_type = TableType.BONDED_PENDING_VIEW

            target_table = self.trade_tables.get(TableType.BONDED_PENDING_VIEW)
            
            if target_table:
                self._assign_widget(widget, target_table)
            success = True
        else: #Never added to our view
            success = self._process_new_token(token_address, TableType.BONDED_PENDING_VIEW)

        return success
    
    class TradeCostBasisInfo:
        def __init_(self, trade_info: TradeInfo):
            self.__init__

    def _handle_trade(self, trade_info: TradeInfo):
        status = True
        token_address = trade_info.token_info.token_address
 
        if trade_info.get_type() == TradeEventType.BUY and not self.active_trades_table.has_id(token_address):
            trade_widget = self.token_widget_map.get(token_address)
  
            if trade_widget: #Cleanup
                table = self.token_table_map.get(token_address)
                table.delete_row(token_address)
  
            metadata = trade_info.token_info.metadata
            tokens_held = trade_info.amount_out.to_ui()
            
            trade_widget = SellTradeWidget(token_address, metadata, tokens_held, "", metadata.program_type, showTokenImage=True)
            trade_widget.set_ranking(0)

            self._assign_widget(trade_widget, self.active_trades_table)

        self.confetti_widget.show_confetti() 

        return status

    def _update_events_queue(self, arg1: MarketAlert):
        self.main_events_queue.put(arg1)

    def __update_table(self, token_address: str):
        table = self.token_table_map.get(token_address)

        if table:
            status_text = self.market_manager.get_status(token_address)
            
            if not status_text:
                status_text = ""
            
            if self.active_trades_table.has_id(token_address):
                status_text += "\n" + self.trades_manager.get_status(token_address)
                profit_loss = self.trades_manager.get_pnl(token_address)

                if profit_loss:
                    self.active_trades_table.set_status(token_address, status_text)
                    self.active_trades_table.set_ranking(token_address, profit_loss.pnl.to_ui())
            else:
                token_value = self.market_manager.get_token_value(token_address, Denomination.USD)

                if token_value:
                    table.set_status(token_address, status_text)
                    table.set_ranking(token_address, token_value.market_cap.to_ui())


    def _unsave_trade(self, mint_address: str):
        if mint_address in self.trade_save_states:
            self.trade_save_states.pop(mint_address)

    def close(self):
        self.txdefitk.shutdown()
        self.root.destroy()
        self.events_thread.stop()
        self.updateStatsThread.stop()
        self.ui_commands_thread.stop()
        self.failed_events_thread.stop()
        pub.unsubscribe(topicName = globals.topic_ui_command, listener = self._handle_ui_command)
        pub.unsubscribe(topicName = globals.topic_trade_event, listener = self._handle_trade_event)        
        pub.unsubscribe(topicName = globals.topic_token_alerts, listener = self._update_events_queue)     

    #def save(self, trade: TradeMonitor): 
    #    self.tradeSaveStates[trade.marketData.mint_address] = {marketDataKey: trade.marketData.to_dict(), tradeDataKey: trade.to_dict()}
    #    
    #    self.state_saver_loader.save_to_file(self.tradeSaveStates) #Replace with database
    
    #def load(self): #TODO redo
    #    tradeStates = self.state_saver_loader.load_from_file()
#
    #    if tradeStates:    
    #        self.tradeSaveStates = tradeStates
#
    #        for dictItem in self.tradeSaveStates.values():
    #            if marketDataKey in dictItem and tradeDataKey in dictItem:
    #                marketDataDict = dictItem[marketDataKey]
    #                tradeDataDict = dictItem[tradeDataKey]
    #                
    #                if self.market_manager:
    #                    marketInfo = self.market_manager.load(marketDataDict)
#
    #                    if marketInfo:
    #                        self.trades_manager.load(tradeDataDict)
    #                        
    #                        self.activeTokens[marketInfo.mint_address] = marketInfo.mint_address
    #                        self._add_purchase(marketInfo.mint_address)
#
    def set_openai_api_key(self, api_key: str):
        if self.ai_agent_widget:
            self.ai_agent_widget.set_api_key(api_key)

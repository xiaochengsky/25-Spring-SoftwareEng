from tkinter import messagebox
import customtkinter as ctk
import TxDefi.Data.Globals as globals
import os
import sys

sys.path.insert(1, os.getcwd()) #needed to access resources outside this folder
from TxDefi.Data.Amount import *
from TxDefi.Data.TradingDTOs import PnlOption
from TxDefi.UI.Components.ViewSelectorFrame import ViewSelectorFrame
from TxDefi.UI.Components.ScrollableFrame import ScrollableFrame

# Define the OrderEntry class
class OrderEntry(ctk.CTkFrame):
    take_profit_abbrv = "TP"
    stop_loss_abbrv = "SP"
    def __init__(self, master, order_type: str, remove_callback, *args, **kwargs):
        super().__init__(master, bg_color=globals.darkBgColor, fg_color=globals.darkBgColor, *args, **kwargs)

        self.remove_callback = remove_callback
        self.order_type = order_type

        # Order Type Label
        self.order_type_label = ctk.CTkLabel(self, text=self.order_type, width=30)
        self.order_type_label.grid(row=0, column=0, padx=5, pady=5)

        if self.order_type == self.take_profit_abbrv:
            placeholder_text = "Take Profit %"
        else:
            placeholder_text = "Stop Loss %"

        # Take Profit Percentage Entry
        self.take_profit_entry = ctk.CTkEntry(self, placeholder_text=placeholder_text, width=100)
        self.take_profit_entry.grid(row=0, column=1, padx=5, pady=5)

        # Amount Percentage Entry
        self.amount_entry = ctk.CTkEntry(self, placeholder_text="Amount %", width=100)
        self.amount_entry.grid(row=0, column=2, padx=5, pady=5)

        # Delete Button
        self.delete_button = ctk.CTkButton(self, text="Delete", width=70, command=self.remove_entry)
        self.delete_button.grid(row=0, column=3, padx=5, pady=5)

    def get_entries(self)->set[str]:
        return (self.take_profit_entry.get(), self.amount_entry.get())
    
    def remove_entry(self):
        self.remove_callback(self)

# Define the OrderManager class
class AdvancedOrderWidget(ViewSelectorFrame):
    market_selection = "Market"
    limit_selection = "Limit"

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, [self.market_selection, self.limit_selection], *args, **kwargs)
        self.order_entries : list[OrderEntry] = []
        self.trailing_tp_sl_checkbox_var = ctk.IntVar()    
        self.selectable_frames : dict[str, ctk.CTkFrame] = {}
        
        #Create Market Frame
        self.market_frame = globals.get_default_frame(self)
        
        #Order Type Selector ComboBox
        self.order_type_var = ctk.StringVar(value="Select Order Type")
        self.order_type_combobox = ctk.CTkComboBox(
            self.market_frame,
            values=[OrderEntry.take_profit_abbrv, OrderEntry.stop_loss_abbrv],
            variable=self.order_type_var,
            width=150,
            state="readonly",
            command=self.add_order_entry  #Set the command to the method
        )
        self.order_type_combobox.grid(row=0, column=0, pady=5, sticky="w")

        #Frame to hold order entries
        self.entries_frame = ScrollableFrame(self.market_frame)
        self.entries_frame.grid(row=1, column=0, pady=10, sticky="nsew")

        checkbox = ctk.CTkCheckBox(self.market_frame, text="Trailing", variable=self.trailing_tp_sl_checkbox_var)
        checkbox.grid(row=2, column=0, pady=5, sticky="w")

        #Create Limit Frame
        self.mcap_entry_var = ctk.StringVar()
        self.limit_frame = globals.get_default_frame(self)
      
        mcap_label = ctk.CTkLabel(self.limit_frame, text="MCAP $")
        mcap_label.grid(row=0, column=0, padx=1, pady=5)
        
        mcap_entry = ctk.CTkEntry(self.limit_frame, placeholder_text="MCAP $", width=150, textvariable=self.mcap_entry_var)
        mcap_entry.grid(row=0, column=1, padx=1, pady=5, sticky="nesw")

        self.selectable_frames[self.market_selection] = self.market_frame
        self.selectable_frames[self.limit_selection] = self.limit_frame
        self.selected_frame = None

        self._on_selection(self.market_selection)

    def hide(self):
        self.market_frame.grid_forget()

    def get_target_mcap(self)->Amount:
        try:
            ret_val = Amount(Value_Type.UI, Amount_Units.USD, float(self.mcap_entry_var.get()), 1)
        except Exception as e:
            ret_val = None

        return ret_val
    
    def reset(self):
        self.mcap_entry_var.set("")

    def is_trailing_checked(self):
        return self.trailing_tp_sl_checkbox_var.get() != 0
        
    def add_order_entry(self, order_type: str):
        if order_type in [OrderEntry.take_profit_abbrv, OrderEntry.stop_loss_abbrv]:
            order_entry = OrderEntry(self.entries_frame.inner_frame, order_type, self.remove_order_entry)
            index = len(self.order_entries)
            order_entry.grid(row=index, column=0, sticky="w", pady=5)
            self.order_entries.append(order_entry)
            self.order_type_var.set("Select Order Type")  # Reset selection

            if order_type == OrderEntry.stop_loss_abbrv:
                current_values = self.order_type_combobox._values
                current_values.remove(OrderEntry.stop_loss_abbrv)
                self.order_type_combobox.configure(values = current_values) #Only allow 1 SP entry

    def remove_order_entry(self, entry: OrderEntry):
        entry.grid_forget()
        self.order_entries.remove(entry)

        if entry.order_type == OrderEntry.stop_loss_abbrv:
            current_values = self.order_type_combobox._values
            current_values.append(OrderEntry.stop_loss_abbrv)
            self.order_type_combobox.configure(values = current_values) #Add the SP entry back
            
    def get_orders(self)->list[PnlOption]:
        orders : list[PnlOption] = []

        for entry in self.order_entries:
            order_type = entry.order_type
            amounts = entry.get_entries()
            try:
                profit_ui = float(amounts[0])         
                amount = Amount.percent_ui(float(amounts[1]))

                if order_type == OrderEntry.take_profit_abbrv:
                    take_profit = Amount.percent_ui(profit_ui)
                else:
                    take_profit = Amount.percent_ui(-profit_ui) #invert percentage so it's treated as a stop loss

                pnl_option = PnlOption(take_profit, amount)
                orders.append(pnl_option)
            except ValueError:
                messagebox.showerror("Input Error", "Please enter valid numbers for percentages.")
                return None
            
        return orders

    def _on_selection(self, selection: str):        
        if self.selected_frame != self.selectable_frames[selection]:
            if self.selected_frame:
                self.selected_frame.grid_remove()

            self.selected_frame = self.selectable_frames[selection]
            self.selected_frame.grid(row=2, column=0, pady=1, sticky="w") #sticky="nesw"    

# Main application setup
if __name__ == "__main__":
    ctk.set_appearance_mode("System")  # Options: "System" (default), "Dark", "Light"
    ctk.set_default_color_theme("blue")  # Options: "blue" (default), "green", "dark-blue"

    root = ctk.CTk()
    root.title("Order Management")

    order_manager = AdvancedOrderWidget(root, width=200, height=150)
    order_manager.pack(fill=ctk.X, expand=False)
    order_manager.pack_propagate(False)
    # Function to retrieve and display orders
    def show_orders():
        orders = order_manager.get_orders()
        if orders is not None:
            for order in orders:
                print(order)

    # Button to print orders to console
    print_orders_button = ctk.CTkButton(root, text="Show Orders", command=show_orders)
    print_orders_button.pack(pady=10)

    root.mainloop()

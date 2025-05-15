import customtkinter as ctk

from TxDefi.Data.Amount import Amount
from TxDefi.UI.Components.AllPurposeTable import AllPurposeTable
from TxDefi.UI.Components.RowWidget import SellTradeWidget
from TxDefi.Abstractions.AbstractTradesManager import AbstractTradesManager
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
import TxDefi.UI.Components.GuiHelperFunctions as gui_functions

class WalletTable(AllPurposeTable):
    def __init__(self, parent: ctk.CTk, sortable: bool, rowlimit: int, style: str, marketManager: AbstractMarketManager, tradeManager: AbstractTradesManager, **kwargs):
        super().__init__(parent, sortable, SellTradeWidget.get_header(), rowlimit, style, **kwargs)
        self.market_manager = marketManager
        self.trades_manager = tradeManager
        self.payer_account = self.trades_manager.get_default_wallet_settings().get_default_signer().get_account_address()
        self.current_amounts : dict[str, Amount] = {}

    def update_table(self):
        token_accounts = self.market_manager.get_tokens_held(self.payer_account)
        last_tokens_held = self.current_amounts.keys()
        current_tokens_held : list[str] = []

        for token_account in token_accounts:
            if token_account.balance.to_ui() >= 1: #Ignore small amounts
                current_tokens_held.append(token_account.mint_address)
                current_token_amount = self.current_amounts.get(token_account.mint_address, Amount.sol_ui(0))

                if current_token_amount.compare(token_account.balance) != 0:
                    if not self.has_id(token_account.mint_address):                       
                        token_info = self.market_manager.get_token_info(token_account.mint_address)
 
                        if token_info:     
                            status = token_account.balance.to_string(7) 
                            trade_widget = SellTradeWidget(token_account.mint_address, token_info.metadata, token_account.balance.to_ui(),
                                                        status, token_info.metadata.program_type, showTokenImage=True)
                            self.insert_row(token_account.mint_address, trade_widget)

                            #image = gui_functions.retrieve_image(token_info.metadata.image_uri)
                            #self._load_image(token_info.token_address, image)   
                    price = self.market_manager.get_price(token_account.mint_address)

                    if price:
                        dollar_value = round(price.to_ui()*token_account.balance.to_ui()*self.market_manager.get_solana_price().to_ui(), 2)
                        status = f"Value: ${dollar_value}\nTokens: {token_account.balance.to_ui()}"

                        self.set_status(token_account.mint_address, status)
                        self.set_ranking(token_account.mint_address, dollar_value)
                        self.current_amounts[token_account.mint_address] = token_account.balance

        #Cleanup    
        remove_list = last_tokens_held - current_tokens_held

        for token_address in remove_list:
            self.delete_row(token_address)
            self.current_amounts.pop(token_address)


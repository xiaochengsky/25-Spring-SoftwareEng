import tkinter as tk
import customtkinter as ctk
import webbrowser
from abc import abstractmethod   
from TxDefi.Data.Globals import TopicHelper
from TxDefi.Data.TradingDTOs import TradeCommand, DeleteCommand
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.MarketEnums import *
from TxDefi.UI.Components.TableCellProperties import ClickableProperty, TextProperty, ImageProperty
import TxDefi.Data.Globals as globals
tradeNumber = 1

class RowWidget:
    def __init__(self, item_id: str):
        self.ranking = 0
        self.item_id = item_id

    def set_ranking(self, ranking):
        self.ranking = ranking

    def get_id(self):        
        return self.item_id    

    def get_ranking(self)->int:        
        return self.ranking    
            
    def get_item(self, col_number)->TextProperty:
        return
    
    @abstractmethod
    def init_row_items(self) -> list:
        pass

class LabelRowWidget(RowWidget):
    def __init__(self, item_id: str, rowItems: list):
        RowWidget.__init__(self, item_id)
        self.rowItems = rowItems

    def init_row_items(self) -> list:
        retList = []  

        for col in self.rowItems:            
            if isinstance(col, str) or isinstance(col, int) or isinstance(col, float):
                retList.append(TextProperty(str(col)))   

        return retList    

class ClickableRowWidget(RowWidget):
    def __init__(self, item_id: str, rowItems: list):
        RowWidget.__init__(self, item_id)
        self.rowItems = rowItems

    def get_item(self, col_index)->TextProperty:
        if col_index < len(self.rowItems):
            return self.rowItems[col_index]
        
    def init_row_items(self) -> list:
        return self.rowItems
        retList = []  

        for col in self.rowItems:            
            if isinstance(col, str) or isinstance(col, int) or isinstance(col, float):
                text = str(col)
                retList.append(TextProperty(text))
            elif isinstance(col, ClickableProperty):
                retList.append(ClickableProperty(col.clickCallback, col.text))

        self.rowItems = retList
        return retList
    
    def handle_callback(self, columnClicked):
        if columnClicked < len(self.rowItems):
            property = self.rowItems[columnClicked]
            
            if isinstance(property, ClickableProperty) and property.clickCallback:
                property.clickCallback(e=None) #TODO may want to handle something other than lambda
    
    #def _create_label_row(self, parent):
    #    labelRow = []
#
    #    font = gui_settings.get_default_font(12, self.isHeader)
    #    px = 50
    #    
    #    for col in self.rowItems:            
    #        if isinstance(col, str) or isinstance(col, int) or isinstance(col, float):
    #            component = tk.Frame(parent, background=self.bg)
    #            label = ctk.CTkLabel(component, text=str(col), font=font, fg_color=self.bg, text_color=self.textColor, padx=px)
    #            label.grid(row = 0, column = 0)
    #        else:
    #            component = col
    #                    
    #        labelRow.append(component)
#
    #    return labelRow
        
class TradeWidget(ClickableRowWidget):
    def __init__(self, item_id: str, metadata: ExtendedMetadata, defaultStatus: str, table_type: TableType, showTokenImage = False):
        ClickableRowWidget.__init__(self, item_id, [])
        self.table_type = table_type
        self.metadata = metadata
        self.token_address = metadata.token_address
        self.show_token_image = showTokenImage
        self.market_status = tk.StringVar(value=defaultStatus)
        self.bonding_status = tk.StringVar(value="")
        self.socials_text = tk.StringVar(value=metadata.socials.to_string())
        self.image_uri = metadata.image_uri  
        self.symbol  = metadata.symbol

        if len(metadata.created_on) == 0:
             self.created_on = globals.default_screener_uri + "/" + self.token_address
        else:    
            self.created_on = metadata.created_on
        self.parent = None
        self.bondingComplete = False

    def load_metadata(self, symbol: str, image_uri: str, created_on: str, socials : list[str] = None)->list:
        self.symbol = symbol
        self.image_uri = image_uri
        self.created_on = created_on
        self.socials = socials

        return self.init_row_items()
    
    def set_bonding_status(self, status: str):
        #if self.rowItems and self.parent:        
        #    rayLogo = gui_functions.create_image_component(ray_logo_path, 26, 30)
        #    imageLabel = ctk.CTkLabel(self.parent, image=rayLogo, cursor="hand2", fg_color=globals.pumpBgColor, text="")
        #    self.rowItems.append(imageLabel)
        self.bonding_status.set(status)
        
        self.bondingComplete = True

    def set_status(self, statusText: str):
        if self.rowItems:
            self.market_status.set(statusText)

    def set_socials_text(self, text: str):
        self.socials_text.set(text)

    def init_row_items(self) -> list:    
        self.rowItems : TextProperty = [] #Store for our own purposes

        # Load the image from a URL
        property = ImageProperty(self.image_uri, None, self.symbol)
        property.show_image = self.show_token_image

        self.rowItems.append(property)

        #self.rowItems.append(TextProperty(self.symbol))
        self.rowItems.append(TextProperty(self.market_status)) #col #2

        open_uri = lambda e: webbrowser.open(self.created_on)
        self.rowItems.append(ClickableProperty(open_uri,  self.socials_text))

        return self.rowItems
    
class BuyTradeWidget(TradeWidget):
    def __init__(self, item_id: str, metadata: ExtendedMetadata, defaultStatus: str, table_type: TableType, showTokenImage = False):
        TradeWidget.__init__(self, item_id, metadata, defaultStatus, table_type, showTokenImage)
        
    def init_row_items(self) -> list:
        super().init_row_items()

        additional_items = []        
        topic_helper = TopicHelper(globals.topic_ui_command)                       

        fast_buy_command = TradeCommand(UI_Command.BUY, self.token_address, None, False, True)  #TODO use default amounts
        property = ClickableProperty(lambda e: topic_helper.send(fast_buy_command), "Fast Buy", styleTag=globals.highlight_green)
        additional_items.append(property)  
        
        deleteCommand = DeleteCommand(UI_Command.DELETE, self.token_address, self.table_type)  
        property = ClickableProperty(lambda e: topic_helper.send(deleteCommand), "X", styleTag=globals.highlight_red)  
        additional_items.append(property)  

        self.rowItems.extend(additional_items)
        self.rowItems.append(TextProperty(self.bonding_status))

        return self.rowItems
    
    @staticmethod
    def get_header():
        return ("Mint", "Stats", "Socials", "Fast Sell", "") 
    
class SellTradeWidget(TradeWidget):
    def __init__(self, item_id: str, metadata: ExtendedMetadata, defaultSourceAmount: float, defaultStatus: str, table_type: TableType, showTokenImage = False):
        TradeWidget.__init__(self, item_id, metadata, defaultStatus, table_type, showTokenImage)
        self.defaultSourceAmount = defaultSourceAmount

    def init_row_items(self) -> list:   
        super().init_row_items()
        additionalItems = []        
        topicHelper = TopicHelper(globals.topic_ui_command)

        fastSellCommand = TradeCommand(UI_Command.SELL, self.token_address, None, False, True) #TODO
        property = ClickableProperty(lambda e: topicHelper.send(fastSellCommand), "Fast Sell", styleTag=globals.highlight_red)  
        additionalItems.append(property)  

        holdCommand = TradeCommand(UI_Command.HOLD, self.token_address, None, False, True)
        property = ClickableProperty(lambda e: topicHelper.send(holdCommand), "Hold", styleTag=globals.highlight_green)    
        additionalItems.append(property)  

        self.rowItems.extend(additionalItems)

        return self.rowItems
    
    @staticmethod
    def get_header():
        return ("Mint", "Stats", "Socials", "Fast Sell")
    
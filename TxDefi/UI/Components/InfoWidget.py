import customtkinter as ctk

#Widget for displaying a header with some information
class InfoWidget(ctk.CTkFrame):
    def __init__(self, parent, infoText: str, infoTextColor: str, bg: str, highlightColor: str, **kwargs):
        super().__init__(parent, bg_color=bg, fg_color=bg, **kwargs)
        self.highlightColor = highlightColor
        self.bgColor = bg
        
        self.infoLabel = ctk.CTkLabel(self, text=infoText, text_color=infoTextColor, bg_color=bg, fg_color=bg)

    def pack(self, **kwargs):
        self.pack_propagate(0)  # Prevent resizing to fit contents
        self._pack_widgets()
        super().pack(**kwargs)

    def _pack_widgets(self):
        self.infoLabel.pack(side=ctk.TOP, fill=ctk.X)

    def highlight(self):
        self.infoLabel.configure(bg_color=self.highlightColor, fg_color=self.highlightColor)
        self.configure(bg_color=self.highlightColor, fg_color=self.highlightColor)
    
    def unhighlight(self):
        self.infoLabel.configure(bg_color=self.bgColor, fg_color=self.bgColor)

    def get_info(self):
        return self.infoLabel._text
    
    def set_info(self, info: str):
        self.infoLabel.configure(text=info)

    def bind_to_event(self, clickType: str, callback):
        self.infoLabel.bind(clickType, callback)

class InfoWidgetWithHeader(InfoWidget):
    def __init__(self, parent, headerText: str, infoText: str, headerTextColor: str, infoTextColor: str, bg: str, highlightColor: str, **kwargs):   
        super().__init__(parent, infoText, infoTextColor, bg, highlightColor, **kwargs) 
        self.headerTextColor = headerTextColor
        self.headerLabel = ctk.CTkLabel(self, text=headerText, text_color=headerTextColor, bg_color=bg, fg_color=bg)

    def _pack_widgets(self):
        self.headerLabel.pack(side=ctk.TOP, fill=ctk.X)
        super()._pack_widgets()

    def get_header(self):
        return self.headerLabel._text
    
    def bind_to_event(self, clickType: str, callback):
        super().bind_to_event(clickType, callback)
        
        self.headerLabel.bind(clickType, callback)

    def highlight(self):
        super().highlight()
        self.headerLabel.configure(bg_color=self.highlightColor, fg_color=self.highlightColor, text_color="white")
    
    def unhighlight(self):
        super().unhighlight()
        self.headerLabel.configure(bg_color=self.bgColor, fg_color=self.bgColor, text_color=self.headerTextColor)

def create_info_row(parent, infoList:list, infoTextColor: str, bg: str, highlightColor: str):
    retList = []
    for value in infoList:
        if isinstance(value, tuple):
            header = value[0]
            info = str(value[1])
        
            infoWidget = InfoWidgetWithHeader(parent, header, info, headerTextColor="white", infoTextColor=infoTextColor, 
                                  bg=bg, highlightColor=highlightColor, width=50, height=50)
        else:                            
            infoWidget = InfoWidget(parent, str(value), infoTextColor=infoTextColor, 
                                  bg=bg, highlightColor=highlightColor, width=35, height=20)
        retList.append(infoWidget)

    return retList

class InfoWidgetRow(ctk.CTkFrame):
    def __init__(self, parent, infoList: list, callback, infoTextColor: str, bg: str, highlightColor: str, isClickable=False):
        super().__init__(parent, bg_color=bg, fg_color=bg)
        self.widgets = create_info_row(self, infoList, infoTextColor, bg, highlightColor)
        self.selectedIndex = 0
        self.callback = callback
        
        for indx in range(len(self.widgets)):   
            self.widgets[indx].pack(side=ctk.LEFT, fill=ctk.X)                         
            
            if isClickable:
                self.widgets[indx].configure(cursor="hand2")
                self.widgets[indx].bind_to_event("<Button-1>", lambda e, interval=indx: self.on_click(interval))
        
        self.widgets[self.selectedIndex].highlight()

    def get_selected_widget(self)->InfoWidget:
        return self.widgets[self.selectedIndex]
    
    def on_click(self, indx):
        self.widgets[self.selectedIndex].unhighlight()

        self.selectedIndex = indx
        
        self.widgets[self.selectedIndex].highlight()

        if self.callback:
            self.callback()
                
import customtkinter as ctk
import TxDefi.Data.Globals as guisettings
from TxDefi.UI.Components.InfoWidget import InfoWidgetRow, InfoWidgetWithHeader, InfoWidget
defaultComponentWidthHeight = (100, 60)

class RatioInfoRow(ctk.CTkFrame):
    def __init__(self, parent, headerText: str, **kwargs):
        super().__init__(parent, **kwargs)

        self.infoFrame = InfoWidgetWithHeader(self, headerText, "0", "white", "white", guisettings.darkBgColor, guisettings.darkBgColor, 
                                              width=defaultComponentWidthHeight[0], height=defaultComponentWidthHeight[1])
        self.infoFrame.pack(side=ctk.LEFT, anchor="w")

        self.ratioInfo = InfoWidget(self, "0:0", "white", guisettings.darkBgColor, guisettings.darkBgColor, height=defaultComponentWidthHeight[1])
        self.ratioInfo.pack(side=ctk.LEFT, anchor="w")
    
        self.ratioBar = create_progress_bar(self.ratioInfo)
        self.ratioBar.set(.6)
        self.ratioBar.pack(side=ctk.TOP)

    def set_info(self, infoText: str, ratioLeft: float, ratioRight: float):
        total = ratioLeft + ratioRight
        self.infoFrame.set_info(infoText)
        self.ratioInfo.set_info(str(ratioLeft) + " : " + str(ratioRight))
                
        ratioPercent = 0 if total == 0 else round(ratioLeft/total, 5)        

        self.ratioBar.set(ratioPercent)

class VolumeWidget(ctk.CTkFrame):
    def __init__(self, parent, columns:list[tuple], callback, **kwargs):
        super().__init__(parent, **kwargs)
        
        #Create Volume Row
        self.volumePercentRow = InfoWidgetRow(self, columns, callback, 
                                              "green", guisettings.darkBgColor,
                                                guisettings.darkHighlightColor, True)
        self.volumePercentRow.pack(side=ctk.TOP, anchor="w")

        #Bottom panel info block
        bottomPanelFrame = ctk.CTkFrame(self, fg_color=guisettings.darkBgColor)
        bottomPanelFrame.pack(side=ctk.TOP, anchor="w")

        self.buysSellsInfo = RatioInfoRow(bottomPanelFrame,  "TXNS")
        self.buysSellsInfo.pack(side=ctk.TOP)

        self.volumeStatsInfo = RatioInfoRow(bottomPanelFrame,  "Volume")
        self.volumeStatsInfo.pack(side=ctk.TOP)
        
        self.makersInfo = InfoWidgetWithHeader(bottomPanelFrame,  "Makers", "0", "white", "white", guisettings.darkBgColor,
                                                guisettings.darkBgColor, width=defaultComponentWidthHeight[0], 
                                                height=defaultComponentWidthHeight[1])
        self.makersInfo.pack(side=ctk.TOP, anchor="w")

    def get_selected_index(self):
        return self.volumePercentRow.selectedIndex    
    
    def configure_volume_info(self, numTransactions: int, totalVolume: float, totalMakers: int, numBuys: int, buyVolume: float):
        numSells = numTransactions - numBuys
        sellVolume = round(totalVolume - buyVolume, 5)
        self.buysSellsInfo.set_info(str(numTransactions), numBuys, numSells)
        self.volumeStatsInfo.set_info(str(totalVolume), buyVolume, sellVolume)
        self.makersInfo.set_info(str(totalMakers)) 

def create_progress_bar(parent)->ctk.CTkProgressBar:
    progressBar = ctk.CTkProgressBar(parent, corner_radius=4, width=180)
    progressBar.configure(progress_color="green", fg_color="red")

    return progressBar

def test():
    pass

def main():
        root = ctk.CTk()
        root.geometry("1450x915")  
        ctk.set_appearance_mode("dark")

        volumeIntervals = [("1M",0), ("5M",0), ("1H",0), ("6H",0), ("24H",0)] 
        vWidget = VolumeWidget(root, volumeIntervals, test)
        vWidget.pack(side=ctk.TOP, fill=ctk.BOTH, anchor="w")

        vWidget.configure_volume_info(133, 3000, 84, 96, 2000)
        root.mainloop()

if __name__ == "__main__":
    main()

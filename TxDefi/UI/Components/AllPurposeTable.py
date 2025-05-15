from PIL import ImageTk
import threading
import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from PIL import Image
from TxDefi.Utilities.ResourceStorage import ResourceStorage
from TxDefi.UI.Components.RowWidget import RowWidget
from TxDefi.UI.Components.TableCellProperties import ClickableProperty, TextProperty, ImageProperty
import TxDefi.Data.Globals as globals

update_interval = 10 #Table has to re-sort at every interval so setting this too low will impair performance

class AllPurposeTable(ttk.Treeview):
    def __init__(self, parent: ctk.CTk, sortable: bool, headerTuple: tuple, rowlimit: int, style: str, **kwargs):
        super().__init__(parent, columns=headerTuple, style=style, **kwargs)
        self.parent = parent
        self.currRowIndex = 0
        self.displayRowLimit = rowlimit
        self.selected_item_id = ""
        self.rowWidgets : dict[str, RowWidget]= {}
        self.lock = threading.Lock()
        self.lastSortedRows = None   
        self.sortable = sortable

        self.stored_images : ResourceStorage = ResourceStorage(10000, 5000)
            
        self.scrollbarHorizontal = ctk.CTkScrollbar(self, orientation="horizontal", command=self.xview)
        self.scrollbarVertical = ctk.CTkScrollbar(self, orientation="vertical", command=self.yview)     
        self.config(xscrollcommand=self.scrollbarHorizontal.set)
        self.config(yscrollcommand=self.scrollbarVertical.set)        

        self.scrollbarHorizontal.pack(side=ctk.BOTTOM, fill=ctk.X, anchor="s")
        self.scrollbarVertical.pack(side=ctk.RIGHT, fill=ctk.Y, anchor="e")
        self.tag_configure(globals.highlight_red, background=globals.redButtonColor, foreground='white')
        self.tag_configure(globals.highlight_green, background=globals.greenButtonColor, foreground='black')
        self.tag_configure(globals.highlightBlue, background='blue', foreground='white')
        
        self.bind("<Button-1>", self.on_click)

        for colIndex in range(len(headerTuple)):
            colId = "#" + str(colIndex)

            self.heading(colId, text=headerTuple[colIndex], anchor=tk.CENTER)
            self.column(colId, width=120, minwidth=25, anchor=tk.CENTER)

        if sortable:
            updateTimer = threading.Timer(update_interval, self._update_task)
            updateTimer.daemon = True
            updateTimer.start()           

    def get_selected_id(self)->str:
        return self.selected_item_id
    
    def _update_task(self):
        with self.lock:
            sortedRows = list(self.rowWidgets.values())[1:]

            sortedRows.sort(key=lambda w: w.get_ranking(), reverse=True)   

            rowsList = sortedRows[:self.displayRowLimit] #Only show top ones for performance reasons

            #print("Update called " + str(len(rowsList)) + " items")
            #if (datetime.now() - self.lastRefreshTime).total_seconds() > 30:
            #    forgetLength = len(sortedRows)-self.displayRowLimit
            #
            #    if forgetLength > 0:
            #        forgetRowsList = sortedRows[-forgetLength:]
            #    
            #        for row in forgetRowsList:
            #            row.destroy()
            #            
            widgetIdsCovered = {}

            for rowIndex, widget in enumerate(rowsList): 
                indexExistsLastList = self.lastSortedRows and rowIndex < len(self.lastSortedRows)

                if not indexExistsLastList: #Check if there is an index in lastSorted Rows
                    shouldUpdate = True
                elif (indexExistsLastList and widget != self.lastSortedRows[rowIndex]):
                    lastId = self.lastSortedRows[rowIndex].item_id
                    if lastId not in widgetIdsCovered: #Check if this widget should be displaced
                        #print("Displaced " +  self.lastSortedRows[rowIndex].item_id)
                        if self.has_id(lastId):
                            self.detach(self.lastSortedRows[rowIndex].item_id)             
                        
                    shouldUpdate = True
                else:
                    shouldUpdate = False
                    
                widgetIdsCovered[widget.item_id] = widget.item_id
                                                
                if shouldUpdate:
                    try:
                        #print("Adding " +  widget.item_id + " to row " + str(rowNumber))
                        self.move(widget.item_id, '', rowIndex)
                        #self.root.after(0, lambda: self.move(widget.item_id, '', rowIndex))
                    except Exception as e:
                        pass
                    #self.__update_row(rowNumber, widget.get_ui_component_tuple(self.scrollableFrame))

            self.lastSortedRows = sortedRows

            update_timer = threading.Timer(update_interval, self._update_task) #TODO use one looping thread instead
            update_timer.daemon = True
            update_timer.start()

    def get_row(self, item_id: str)->RowWidget:      
        with self.lock: 
            if item_id in self.rowWidgets:
                return self.rowWidgets[item_id]    
    
    def has_id(self, item_id: str)->bool:
        return item_id in self.rowWidgets
    
    def set_ranking(self, mintAddress: str, ranking):
        with self.lock:    
            if self.has_id(mintAddress):
                row = self.rowWidgets[mintAddress]

                if row.get_ranking() != ranking:
                    row.set_ranking(ranking)

    def set_status(self, item_id: str, statusText: str):
        with self.lock:
            if self.has_id(item_id):
                self.rowWidgets[item_id].set_status(statusText)
                self._update_row(item_id, 0, statusText)

    def set_socials(self, item_id: str, socials_text: str):
        with self.lock:
            if self.has_id(item_id):
                self.rowWidgets[item_id].set_socials_text(socials_text)
                self._update_row(item_id, 1, socials_text)
        
    #Append a ui component to a row
    def get_widget(self, item_id: str):
        with self.lock:
            if item_id in self.rowWidgets:
                return self.rowWidgets[item_id]

    def _update_row(self, item_id: str, columnIndex: int, newValue: str):
        # Retrieve items with the specified tag ; col indexes for editable fields starts at a decrement of of 2      
        values = list(self.item(item_id, 'values'))
        values[columnIndex] = newValue
        self.item(item_id, values=values)
    
    def _load_image(self, item_id: str, image: Image):
        try:              
            photo_image = ImageTk.PhotoImage(image)                

            if photo_image:                       
                with self.lock:
                    if self.has_id(item_id):
                        self.item(item_id, image=photo_image, text="") #Image replaces text
                        self.stored_images.add_resource(item_id, photo_image)

        except Exception as e:
            print("AllpurposeTable: issue with loading image " + str(e))
    
    def load_image(self, item_id: str, image: Image):
        #self.insert("", tk.END, iid=item_id, values=valueList, tags=allTags)                    
        #loadImageThread = threading.Thread(target=self._load_image, args=(item_id, image), daemon=True)
        #loadImageThread.start()                       
        self._load_image(item_id, image)              

    def insert_row(self, item_id: str, item: RowWidget, tags = []):
        with self.lock:
            if item_id not in self.rowWidgets:
                self.rowWidgets[item_id] = item 
                
                image_path = None
                rowTuple = item.init_row_items()
                valueList = []
                allTags = ['centered']

                if tags:
                    allTags.extend(tags)

                cellTags = {}
                for colItem in rowTuple:
                    if isinstance(colItem, ImageProperty) and colItem.show_image and len(colItem.image_path) > 0:
                        image_path = colItem.image_path
                    
                    if isinstance(colItem, TextProperty):
                        if isinstance(colItem, ClickableProperty):
                            cellTags[item_id] = colItem.styleTag

                        if isinstance(colItem.text, tk.StringVar) or isinstance(colItem.text, ctk.StringVar):
                            valueList.append(colItem.text.get()) #TODO link so we never have to update it manually
                        else: 
                            valueList.append(colItem.text)

                self.insert("", tk.END, iid=item_id, text=valueList[0], values=valueList[1:], tags=allTags)
                
#                if image_path:                          
#                    image = gui_functions.retrieve_image(image_path)           
#                    if image:
#                        self.load_image(item_id, image)  

                #for key in cellTags: #Doesn't work
                #   self.item(key, tags=[guisettings.highlightBlue, cellTags[key]])

    def delete_row(self, item_id: str):
        with self.lock: 
            if item_id in self.rowWidgets:
                self.rowWidgets.pop(item_id)
                
                self.delete(item_id)   

    def on_click(self, event):
        # Get the region and item that was clicked
        region = self.identify("region", event.x, event.y)        
        item_id = self.identify_row(event.y)
        column = self.identify_column(event.x)

        if item_id in self.rowWidgets:
            self.selected_item_id = item_id
            row_widget : RowWidget = self.rowWidgets[item_id]          
           
            # Get the bounding box of the cell
            #x, y, width, height = self.bbox(item_id, column)
            
            #print("Clicked " + str(x) + "," + str(y))
            try:            
                columnIndex = int(column.replace('#', ''))
                
                #if item_id in self.images and isinstance(row_widget.get_item(0), ImageProperty):
                #    columnIndex += 1 #2nd column is hidden since image took it over, so add an offset here

                row_widget.handle_callback(columnIndex)
            except Exception:
                pass #Sometimes this happens for whatever reason
            # Place the Frame in the cell
            #frame.place(x=x, y=y, width=width, height=height)
from PIL import Image, ImageTk
from io import BytesIO
import customtkinter as ctk
import webbrowser
import requests
from tkinter import ttk
import TxDefi.Utilities.LoggerUtil as logger_util
import TxDefi.Data.Globals as guisettings
showImage = False
padx = 40

def set_default_treeview_style(removeHighlight)->str:
    # Create a style object #TODO Move to gui settings
    style = ttk.Style()
    style.theme_use("clam")
    #Configure the Treeview style
    style.configure(guisettings.tableStyleId,
                    background=guisettings.darkBgColor, # Background color
                    fieldbackground=guisettings.darkBgColor, foreground = "white",  # Field background color
                    rowheight=118)  # Text color
    
    if removeHighlight:
        style.map(guisettings.tableStyleId,       
        background=[('selected', guisettings.panelBgColor)],  # Remove highlight color
        fieldbackground=guisettings.panelBgColor,
        foreground=[('selected', 'white')])  # Keep text color white
    
    style.configure("Treeview.Heading", background=guisettings.darkBgColor, foreground="white", font=("Helvetica", 10, "bold"))

    return guisettings.tableStyleId

def create_image_component(imageData: str, width = 80, height = 80)->ImageTk.PhotoImage:
    try:
        img = Image.open(imageData).resize((width, height))
        
        return ImageTk.PhotoImage(img) #ctk.CTkImage(img, size=(width, height))# 
    except Exception as e:    
        logger_util.logger.info("Bad image format at " + str(imageData) + " Exception: " + str(e))

def create_ctk_image_component(image_data: str, width = None, height = None)->ctk.CTkImage:
    try:
        img = Image.open(image_data)
 
        if width and height:
            img.resize((width, height))

        return ctk.CTkImage(img)
    except Exception as e:    
        logger_util.logger.info("Bad image format at " + str(image_data) + " Exception: " + str(e))

def create_icon_button(parent, image_data: str, width = 10, height = 10)->ctk.CTkButton:    
    config_logo = create_ctk_image_component(image_data)
    return ctk.CTkButton(parent, width=width, height=height, image=config_logo, fg_color="transparent", hover=False, text="", command=lambda: print("Feature is in work"))

def retrieve_image(image_uri: str)->Image:
    try:        
        response = requests.get(image_uri, timeout=5)
        img_data = BytesIO(response.content)
        image = Image.open(img_data)
        content_type = response.headers.get("Content-Type")
        
        if content_type and content_type == "image/gif":
            image = image.convert("RGBA")

        return image.resize((80, 80)) #create_image_component(imgData)
    except requests.exceptions.Timeout as e:
        print("Request timed out for " + image_uri + " Exception: " + str(e))
    except requests.exceptions.RequestException as e:
        print("Problem loading  " + image_uri + " Exception: " + str(e))
    except Exception as e:
        print("Unknown Error: " + str(e))

def create_url_label(parent, name, url: str, bg = None, textColor = "white")->ctk.CTkLabel:
    if bg:
        url_label = ctk.CTkLabel(parent, text=name, text_color=textColor, bg_color=bg, fg_color=bg, cursor="hand2")
    else:
        url_label = ctk.CTkLabel(parent, text=name, text_color=textColor, cursor="hand2")

    buttonSequence = f"<Button-1>"
    url_label.bind(buttonSequence, lambda e: webbrowser.open(url))

    return url_label

def create_url_label_grid(parent, url: str, iRow: int, iCol: int)->ctk.CTkLabel:
    url_label = ctk.CTkLabel(parent, text=url, text_color="blue", cursor="hand2")
    url_label.grid(row=iRow, column=iCol, sticky='ew')
    buttonSequence = f"<Button-{iRow+1}>"
    url_label.bind(buttonSequence, lambda e: webbrowser.open(url))

    return url_label

def create_view_change_label(parent, actionManager, labelText, frameIndex, textColor="grey")->ctk.CTkLabel:
    active_trades_label =  ctk.CTkLabel(parent, text=labelText, cursor="hand2", text_color=textColor)
    active_trades_label.bind("<Button-1>", lambda e: actionManager._change_view_frame(frameIndex))

    return active_trades_label


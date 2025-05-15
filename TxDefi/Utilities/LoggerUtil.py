
import tkinter as tk
import logging

logger = logging.getLogger()

class TextHandler(logging.Handler):
    """This class allows you to log messages to a Tkinter Text or ScrolledText widget"""
    def __init__(self, textWidget):
        super().__init__()
        self.text_widget = textWidget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.config(state=tk.DISABLED)
            self.text_widget.yview(tk.END)
        self.text_widget.after(0, append)

def init_logger(logDisplay):
    # Create a logger
    logger.setLevel(logging.INFO)
    # Create a handler that logs to the scrolled text widget
    textHandler = TextHandler(logDisplay)
    textHandler.setLevel(logging.INFO)
    # Create a formatter and set it for the handler
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    textHandler.setFormatter(formatter)
    # Add the handler to the logger
    logger.addHandler(textHandler)
    #logger.addHandler(logging.StreamHandler()) 
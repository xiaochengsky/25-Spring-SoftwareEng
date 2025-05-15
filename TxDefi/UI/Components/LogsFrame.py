import customtkinter as ctk
import tkinter as tk

class LogsFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.create_widgets()

    def create_widgets(self):
        # Create a Text widget for displaying logs
        self.log_display = tk.Text(self, wrap=tk.WORD, state='normal', height=15, width=96, background='black', foreground='white')
        self.log_display.pack(side=tk.LEFT, fill=tk.BOTH, expand= True)
        self.log_display.config(state=tk.DISABLED)

        # Create a Scrollbar and attach it to the Text widget
        scrollbar = ctk.CTkScrollbar(self, command=self.log_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_display.config(yscrollcommand=scrollbar.set)

        # Enable text selection for copying
        self.log_display.bind("<1>", lambda event: self.log_display.focus_set())

    def get_log_display(self):
        return self.log_display
    
    def add_text(self, text: str):
        self.log_display.insert(tk.END, text)


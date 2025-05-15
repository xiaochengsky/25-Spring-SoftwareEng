from abc import abstractmethod
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk


class ClickCallbackHandler:
    def __init__(self, component_id: str):
        self.id = component_id

    @abstractmethod
    def handle_click(self, button_text: str): #TODO could use an event instead of the button text, but this works for now
        print(f"Toggle: {self.id} {button_text}")

class ToggleButton(ctk.CTkButton):
    def __init__(self, master, callback_handler: ClickCallbackHandler, text_on="On", text_off="Off", **kwargs):
        super().__init__(master, **kwargs)
        self.text_on = text_on
        self.text_off = text_off
        self.state = False  # Starts in 'off' state
        self.callback_handler = callback_handler
        self.configure(text=self.text_off, command=self.toggle)

    def toggle(self):
        self.state = not self.state
        new_text = self.text_on if self.state else self.text_off

        self.callback_handler.handle_click(new_text)
        self.configure(text=new_text)

class CustomCtkTable(ctk.CTkFrame):
    def __init__(self, master, columns: dict, **kwargs):
        """
        columns: list of dicts. Each dict defines:
            - "header": str
            - "type": "string" | "checkbox" | "button"
            - "button_text" (optional): default text for buttons
            - "image" (optional): path to image file (for buttons only)
            - "command" (optional): callable (for buttons only)
        """
        super().__init__(master, **kwargs)
        self.columns = columns
        self.rows : dict[str, list[any]] = {}
        self.column_count = len(columns)

        # Create canvas + scrollbar
        self.canvas = tk.Canvas(self, borderwidth=0, background="#2b2b2b", highlightthickness=0)
        self.scrollbarHorizontal = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.scrollbarVertical = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)
        self.canvas.configure(xscrollcommand=self.scrollbarHorizontal.set, yscrollcommand=self.scrollbarVertical.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbarHorizontal.pack(side="bottom", fill="x")
        self.scrollbarVertical.pack(side="right", fill="y")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Add headers inside scrollable frame
        for idx, col in enumerate(columns):
            lbl = ctk.CTkLabel(self.scrollable_frame, text=col["header"], anchor="w", font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=0, column=idx, padx=5, pady=(0, 10), sticky="w")
            self.scrollable_frame.grid_columnconfigure(idx, weight=1)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    @staticmethod
    def is_col_valid(col_type: str):
        return col_type == "string" or col_type == "checkbox" or col_type == "button" or col_type == "x"
    
    def insert_row(self, id: str, items : list[any]):
        """
        values: list of values corresponding to column types
            for 'string': string
            for 'checkbox': bool
            for 'button': overrides button text (optional)
        """
        if id not in self.rows and len(items) <= len(self.columns):
            row_widgets = []
            row_index = len(self.rows) + 1  # +1 because row 0 is header

            for col_index, col in enumerate(self.columns):
                col_type = col["type"]
                val = items[col_index]

                if self.is_col_valid(col_type):
                    ui_component = None

                    if isinstance(val, str):
                        ui_component = ctk.CTkLabel(self.scrollable_frame, text=val, anchor="w")
                    elif col_type == "checkbox":
                        var = tk.BooleanVar(value=bool(val))
                        ui_component = ctk.CTkCheckBox(self.scrollable_frame, variable=var, text="")
                    elif isinstance(val, ctk.CTkButton):
                        ui_component = val
                    else:
                        ui_component = ctk.CTkButton(self.scrollable_frame, text="❌")
                        ui_component.bind("<Button-1>", lambda e: self.delete_row(id))

                    if ui_component:
                        ui_component.grid(row=row_index, column=col_index, padx=1, pady=5, sticky="w")
                        row_widgets.append(ui_component)

            self.rows[id] = row_widgets
        
    def delete_row(self, id: str):
        if id in self.rows:
            cells = self.rows.pop(id)

            for widget in cells:
                widget.destroy()

            # Shift remaining rows up in the grid
            rows_list = list(self.rows.values())
            for i in range(len(rows_list)):
                for col_index, widget in enumerate(rows_list[i]):
                    widget.grid_configure(row=i + 1) # +1 because row 0 is header
                    
# Example usage
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.geometry("600x400")

    def on_click():
        print("Button clicked!")

    table = CustomCtkTable(root, columns=[
        {"header": "Created", "type": "string"},
        {"header": "Name", "type": "string"},
        {"header": "Status", "type": "string"},
        {"header": "Action", "type": "button"},
        {"header": "", "type": "x"}
    ])
    table.pack(fill="both", expand=True, padx=20, pady=20)

    # Add some rows
    table.insert_row("1", ["178388388", "Alice", "status", ToggleButton(table.scrollable_frame, ClickCallbackHandler("1")), None])
    table.insert_row("2", ["178388388", "Bob", "status", ToggleButton(table.scrollable_frame, ClickCallbackHandler("2")), None])
    table.insert_row("3", ["178388388", "Charlie", "status", ToggleButton(table.scrollable_frame, ClickCallbackHandler("3")), None])

    root.mainloop()

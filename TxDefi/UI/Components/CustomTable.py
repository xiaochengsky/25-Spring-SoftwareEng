import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk

class CustomTable(ctk.CTkFrame):
    def __init__(self, master, columns, **kwargs):
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
        self.rows = []
        self.column_count = len(columns)

        # Create canvas + scrollbar
        self.canvas = tk.Canvas(self, borderwidth=0, background="#2b2b2b", highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
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

    def add_row(self, id: str, values):
        """
        values: list of values corresponding to column types
            for 'string': string
            for 'checkbox': bool
            for 'button': overrides button text (optional)
        """
        row_widgets = []
        row_index = len(self.rows) + 1  # +1 because row 0 is header

        for col_index, col in enumerate(self.columns):
            col_type = col["type"]
            val = values[col_index] if col_index < len(values) else ""

            if col_type == "string":
                lbl = ctk.CTkLabel(self.scrollable_frame, text=val, anchor="w")
                lbl.grid(row=row_index, column=col_index, padx=5, pady=5, sticky="w")
                row_widgets.append(lbl)

            elif col_type == "checkbox":
                var = tk.BooleanVar(value=bool(val))
                chk = ctk.CTkCheckBox(self.scrollable_frame, variable=var, text="")
                chk.grid(row=row_index, column=col_index, padx=0, pady=5)
                row_widgets.append(chk)

            elif col_type == "button":
                btn_text = str(val) if val else col.get("button_text", "Click")
                img = None
                if "image" in col:
                    pil_img = Image.open(col["image"]).resize((16, 16), Image.ANTIALIAS)
                    img = ImageTk.PhotoImage(pil_img)
                    col["tk_img"] = img  # Prevent garbage collection

                btn = ctk.CTkButton(self.scrollable_frame, text=btn_text, image=img if img else None,
                                    command=col.get("command"))
                btn.grid(row=row_index, column=col_index, padx=5, pady=5)
                row_widgets.append(btn)

        self.rows.append(row_widgets)
        
    def delete_row(self, index):
        """Deletes a row by index (0-based, not including header)."""
        if 0 <= index < len(self.rows):
            for widget in self.rows[index]:
                widget.destroy()
            self.rows.pop(index)

            # Shift remaining rows up in the grid
            for i in range(index, len(self.rows)):
                for col_index, widget in enumerate(self.rows[i]):
                    widget.grid_configure(row=i + 1)  # +1 because row 0 is header
# Example usage
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.geometry("600x400")

    def on_click():
        print("Button clicked!")

    table = CustomTable(root, columns=[
        {"header": "Created", "type": "string"},
        {"header": "Name", "type": "string"},
        {"header": "Active", "type": "checkbox"},
        {"header": "Status", "type": "string"},
        {"header": "Action", "type": "button", "button_text": "Launch", "command": on_click}
    ])
    table.pack(fill="both", expand=True, padx=20, pady=20)

    # Add some rows
    table.add_row(["178388388", "Alice", True, "status", None])
    table.add_row(["178388388", "Bob", False, "status", "Details"])
    table.add_row(["178388388", "Charlie", True, "status", None])

    root.mainloop()

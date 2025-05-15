import customtkinter as ctk
import tkinter as tk

class ScrollableFrame(ctk.CTkFrame):
    def __init__(self, parent, width=150, height=100, *args, **kwargs):
        super().__init__(parent, width=width, height=height, *args, **kwargs)
        
        # Get the correct background color for the current theme
        if isinstance(self._bg_color, list):  # If it's a tuple (light mode, dark mode)
            bg_color = self._bg_color[0] if ctk.get_appearance_mode() == "Light" else self._bg_color[1]
        else:
            bg_color = self._bg_color
        # Create a canvas and a scrollbar
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="y", expand=False)
        self.scrollbar.pack(side="right", fill="y")

        # Create an inner frame inside the canvas
        self.inner_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")  
        self.frame_id = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        # Bind resizing events
        self.inner_frame.bind("<Configure>", self.update_scroll_region)
        self.canvas.bind("<Configure>", self.resize_frame)
        self.bind_mouse_wheel()

    def bind_mouse_wheel(self):
        """ Enable scrolling with the mouse wheel """
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows/Mac
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)  # Linux (scroll up)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)  # Linux (scroll down)

    def _on_mousewheel(self, event):
        """ Scroll the canvas when the mouse wheel moves """
        if event.num == 4:  # Linux Scroll Up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux Scroll Down
            self.canvas.yview_scroll(1, "units")
        else:  # Windows/Mac Scroll
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def update_scroll_region(self, event=None):
        """ Update scroll region when content changes """
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def resize_frame(self, event):
        """ Adjust frame width to match canvas width dynamically """
        self.canvas.itemconfig(self.frame_id, width=event.width)

# Main application
#root = ctk.CTk()
#root.geometry("500x400")
#
#scrollable_frame = ScrollableFrame(root, width=50, height=20)
#scrollable_frame.pack(pady=20, padx=20, fill="both", expand=True)
#
## Add many widgets inside the scrollable frame
#for i in range(30):
#    label = ctk.CTkLabel(scrollable_frame.inner_frame, text=f"Item {i+1}")
#    label.grid(row=i, column=0, sticky="w", pady=5)
#
#root.mainloop()

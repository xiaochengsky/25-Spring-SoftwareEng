from abc import abstractmethod
from enum import Enum
import customtkinter as ctk
import TxDefi.Data.Globals as globals

class TpSlView(Enum):
    MARKET_VIEW = 0
    LIMIT_VIEW = 1

class ViewSelectorFrame(ctk.CTkFrame):
    def __init__(self, master, selections: list[str], *args, **kwargs):
        super().__init__(master, bg_color=globals.darkBgColor, fg_color=globals.darkBgColor, *args, **kwargs)
        self.selectable_menu_items = selections
        self.labels : dict[int, ctk.CTkLabel] = {}
        self.curr_selected_view_id = 0

        main_frame = globals.get_default_frame(self)   
        main_frame.grid(row=0, column=0, sticky='w')
    
        for i in range(len(selections)):
            label = ViewSelectorFrame.create_view_change_label(main_frame, self, selections[i], i)
            self.labels[i] = label
            label.pack(side=ctk.LEFT, padx=5, pady=5)

        self._set_view_label(self.curr_selected_view_id, "white")

    def _change_view_frame(self, view_id: int):
        if view_id != self.curr_selected_view_id:
            self._set_view_label(self.curr_selected_view_id, "grey")
            self._set_view_label(view_id, "white")
            self.curr_selected_view_id = view_id
            
            self._on_selection(self.selectable_menu_items[view_id])
    
    def _set_view_label(self, view_id: int, color: str):
        if view_id in self.labels:
            self.labels[view_id].configure(text_color=color)

    @abstractmethod
    def _on_selection(self, selection: str):
        pass

    @staticmethod
    def create_view_change_label(parent, action_manager: "ViewSelectorFrame", label_text: str, frame_index: int, text_color="grey")->ctk.CTkLabel:
        active_trades_label =  ctk.CTkLabel(parent, text=label_text, cursor="hand2", text_color=text_color)
        active_trades_label.bind("<Button-1>", lambda e: action_manager._change_view_frame(frame_index))

        return active_trades_label
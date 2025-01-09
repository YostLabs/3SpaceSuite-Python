import dearpygui.dearpygui as dpg
from dpg_ext.staged_view import StagedView
from dpg_ext.global_lock import dpg_lock

"""
Create a button that can have multiple states, each with
their own callback, style, and label
"""
class DynamicButton(StagedView):

    def __init__(self):
        self.__buttons = {}
        self.default_button = None
        self.active_button = None

        self._stage_id = dpg.add_stage(label="Dynamic Button Stage")

    def add_button(self, key, button, active = False, default = False, move = False):
        if key in self.__buttons:
            raise ValueError("Button Key Already Exists")
        with dpg_lock():
            if not move:
                dpg.configure_item(button, parent=self._stage_id) #Use this version when it works AKA when doing setup
            else:
                dpg.move_item(button, parent=self._stage_id) #This is VERY slow, but necessary if the item already exists
            dpg.configure_item(button, show=False)
            self.__buttons[key] = button
            if default or self.default_button is None:
                self.default_button = button
            if active or self.active_button is None:
                if self.active_button is not None:
                    dpg.configure_item(self.active_button, show=False)
                self.active_button = button
                dpg.configure_item(button, show=True)

    def set_button(self, key):
        with dpg_lock():
            if self.active_button is not None:
                dpg.configure_item(self.active_button, show=False)
            dpg.configure_item(self.__buttons[key], show=True)
            self.active_button = self.__buttons[key]



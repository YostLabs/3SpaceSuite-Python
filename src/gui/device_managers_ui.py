from managers.device_managers import ThreespaceManager
import dearpygui.dearpygui as dpg
from gui.core_ui import StagedView

class ThreespaceManagerToolbar(StagedView):

    def __init__(self, manager: ThreespaceManager):
        self.manager = manager
        self.settings = manager.settings
        with dpg.stage(label="TS-Manager Stage") as self._stage_id:
            with dpg.menu(label="Serial"):
                self.serial_enabled = dpg.add_checkbox(label="Enabled", default_value=self.settings.serial.enabled, callback=self.__on_serial_enable_changed)
                self.show_unknown_serial_box = dpg.add_checkbox(label="Show Unknown", default_value=self.settings.serial.show_unknown, callback=self.__on_show_unknown_changed)
            with dpg.menu(label="BLE"):
                self.ble_enabled = dpg.add_checkbox(label="Enabled", default_value=self.settings.ble.enabled, callback=self.__on_ble_enable_changed)
                self.hidden_enabled = dpg.add_checkbox(label="Show Hidden", default_value=self.settings.ble.show_hidden, callback=self.__on_show_hidden_changed)
                self.filter_input = dpg.add_input_text(label="Filter", default_value=self.settings.ble.filter, callback=self.__on_filter_changed)
        self.__update_state()
    
    def __on_serial_enable_changed(self, sender, app_data):
        self.settings.serial.enabled = app_data

    def __on_show_unknown_changed(self, sender, app_data):
        self.settings.serial.show_unknown = app_data        
    
    def __on_ble_enable_changed(self, sender, app_data):
        self.settings.ble.enabled = app_data
        self.__update_state()

    def __on_show_hidden_changed(self, sender, app_data):
        self.settings.ble.show_hidden = app_data
        self.__update_state()

    def __on_filter_changed(self, sender, app_data):
        self.settings.ble.filter = app_data
    
    def __update_state(self):
        dpg.configure_item(self.hidden_enabled, enabled=True)
        dpg.configure_item(self.filter_input, enabled=True)
        if not self.settings.ble.enabled:
            dpg.configure_item(self.hidden_enabled, enabled=False)
            dpg.configure_item(self.filter_input, enabled=False)
        else:
            dpg.configure_item(self.filter_input, enabled=not self.settings.ble.show_hidden)
    

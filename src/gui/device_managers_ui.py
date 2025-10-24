from managers.device_managers import ThreespaceManager, BleSettings, ThreespaceBLENordicUartProfile
import dearpygui.dearpygui as dpg
import dpg_ext.extension_functions as dpgext
from gui.core_ui import StagedView
from typing import Callable
import re

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
                self.profile_button = dpg.add_button(label="Modify Profiles", callback=self.__on_modify_profiles_button)
        self.__update_state()

        self.profile_window: ProfileWindow = None
    
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
    
    def __on_modify_profiles_button(self, sender, app_data):
        if self.profile_window is None:
            self.profile_window = ProfileWindow(self.settings.ble.profiles, self.__on_profile_window_closed)

    def __on_profile_window_closed(self, profiles: list[ThreespaceBLENordicUartProfile]):
        self.profile_window = None

        modified = len(profiles) != len(self.settings.ble.profiles) #Check for length first
        if not modified: #Now check for changes
            for i in range(len(profiles)):
                if profiles[i] != self.settings.ble.profiles[i]:
                    modified = True
                    break
        
        if modified:
            self.manager.set_ble_registrations(profiles)

    def __update_state(self):
        dpg.configure_item(self.hidden_enabled, enabled=True)
        dpg.configure_item(self.filter_input, enabled=True)
        if not self.settings.ble.enabled:
            dpg.configure_item(self.hidden_enabled, enabled=False)
            dpg.configure_item(self.filter_input, enabled=False)
        else:
            dpg.configure_item(self.filter_input, enabled=not self.settings.ble.show_hidden)
    

class ProfileWindow:

    def __init__(self, profiles: list[ThreespaceBLENordicUartProfile], close_callback: Callable[[list[ThreespaceBLENordicUartProfile]],None]):
        with dpg.window(modal=False, no_move=False, no_resize=False, label="Profile Manager", no_close=False,
                        width=800, height=400, on_close=self.__on_close) as self.modal:
            with dpg.child_window(height=-32) as self.selection_window:
                pass
            with dpg.table(header_row=False):
                dpg.add_table_column()
                dpg.add_table_column()
                with dpg.table_row():
                    dpg.add_button(label="Add", width=-1, callback=self.__on_create_profile)
                    dpg.add_button(label="Remove", width=-1, callback=self.__on_remove_profile)                                                    

        self.last_opened_node = None
        with dpg.item_handler_registry() as self.toggled_open_handler:
            dpg.add_item_toggled_open_handler(callback=self.__on_profile_toggled_open)

        self.on_close = close_callback

        #Tree node to profile
        self.bindings: dict[int,ThreespaceBLENordicUartProfile] = {}
        for profile in profiles:
            self.add_profile(profile)

    def add_profile(self, profile: ThreespaceBLENordicUartProfile):
        dpg.push_container_stack(self.selection_window)
        with dpg.tree_node(label=profile.SERVICE_UUID, selectable=True) as tree_node:
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=70)
                dpg.add_table_column()
                with dpg.table_row():
                    dpg.add_text("RX UUID:")
                    dpg.add_text(profile.RX_UUID)
                with dpg.table_row():
                    dpg.add_text("TX UUID:")
                    dpg.add_text(profile.TX_UUID)                    
        dpg.pop_container_stack()
        dpg.bind_item_handler_registry(tree_node, self.toggled_open_handler)
        dpg.set_item_user_data(tree_node, tree_node)
        self.bindings[tree_node] = profile

    def __on_create_profile(self):
        popup = dpgext.PopupWindow(title="Register UUIDS", width=450)
        with popup:
            with dpg.table(header_row=False):
                dpg.add_table_column(init_width_or_weight=70, width_fixed=True)
                dpg.add_table_column()
                with dpg.table_row():
                    dpg.add_text("Service:")
                    service_input = dpg.add_input_text(width=-1, hint="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
                with dpg.table_row():
                    dpg.add_text("RX:")
                    rx_input = dpg.add_input_text(width=-1, hint="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
                with dpg.table_row():
                    dpg.add_text("TX:")
                    tx_input = dpg.add_input_text(width=-1, hint="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")   
        
        validate_uuid_expression = re.compile("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

        def on_confirm():
            service = dpg.get_value(service_input)
            rx = dpg.get_value(rx_input)
            tx = dpg.get_value(tx_input)
            new_profile = ThreespaceBLENordicUartProfile(service, rx, tx)

            for node in self.bindings:
                profile = self.bindings[node]
                if profile.SERVICE_UUID == new_profile.SERVICE_UUID:
                    if profile == new_profile: #DUPLICATE
                        return
                    else: #Remove and update values
                        self.remove_profile(node)
                        break
            self.add_profile(new_profile)
            popup.delete()

        confirm_button = dpgext.PopupButton(label="Confirm", callback=on_confirm, close_on_select=False)
        cancel_button = dpgext.PopupButton(label="Cancel", callback=None, close_on_select=True)

        def on_modified():
            service = dpg.get_value(service_input)
            rx = dpg.get_value(rx_input)
            tx = dpg.get_value(tx_input)

            service_valid = validate_uuid_expression.fullmatch(service)
            rx_valid = validate_uuid_expression.fullmatch(rx)
            tx_valid = validate_uuid_expression.fullmatch(tx)
            if service_valid and rx_valid and tx_valid:
                dpg.enable_item(confirm_button.tag)
            else:
                dpg.disable_item(confirm_button.tag)
        
        dpg.set_item_callback(service_input, on_modified)
        dpg.set_item_callback(rx_input, on_modified)
        dpg.set_item_callback(tx_input, on_modified)

        popup.add_buttons([confirm_button, cancel_button])                                   
        dpg.disable_item(confirm_button.tag)

    def __on_profile_toggled_open(self, handler, sender, user_data):
        new_node = None

        #Find which node was just opened
        for node in self.bindings:
            if dpg.get_value(node) and node != self.last_opened_node:
                new_node = node
                break
        
        #The opened one didn't change
        if new_node is None:
            return

        #Close all other nodes
        self.last_opened_node = new_node
        for node in self.bindings:
            if node == self.last_opened_node: continue
            dpg.set_value(node, False)
    
    def get_active_node(self):
        for node in self.bindings:
            if dpg.get_value(node):
                return node
        return None  

    def get_active_profile(self):
        node = self.get_active_node()
        if node is None: return None
        return self.bindings[node]

    def get_profiles(self):
        return list(self.bindings.values())

    def remove_profile(self, node: int):
        dpg.delete_item(node)
        del self.bindings[node]  

    def __on_remove_profile(self):
        selected_node = self.get_active_node()
        if selected_node is None:
            return
        self.remove_profile(selected_node)

    def __on_close(self):
        dpg.delete_item(self.toggled_open_handler)
        dpg.delete_item(self.modal)

        self.on_close(self.get_profiles())
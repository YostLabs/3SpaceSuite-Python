import dearpygui.dearpygui as dpg
from dpg_ext.global_lock import dpg_lock
from dpg_ext.themes import create_theme_imgui_dark, create_theme_imgui_light, create_theme_imgui_default

from general_managers import GeneralManager
from device_managers import DeviceManager
from settings_manager import SettingsManager

from utility import Logger
import traceback

import platform
import pathlib
import os
import shutil
import re
import json

class MenuBar:

    def __init__(self, parent, general_manager: GeneralManager):
        if parent is not None:
            dpg.push_container_stack(parent)
        
        with dpg.menu(label="View"):
            dpg.add_menu_item(label="Start Window", callback=self.__load_start_window)
            with dpg.menu(label="Theme"):
                self.theme_radio = dpg.add_radio_button(items=["Default", "Dark", "Light"], callback=self.__set_theme, default_value="Default")
            dpg.add_menu_item(label="Style", callback=dpg.show_style_editor)
            dpg.add_menu_item(label="Fonts", callback=dpg.show_font_manager)

        with dpg.menu(label="Tools"):
            #dpg.add_menu_item(label="Discover Ports", callback=self.__discover_ports)
            dpg.add_menu_item(label="Metrics", callback=dpg.show_metrics)
            dpg.add_menu_item(label="Registry", callback=dpg.show_item_registry)

        if parent is not None:
            dpg.pop_container_stack()

        self.general_manager = general_manager
        self.device_manager = general_manager.device_manager
        self.file_explorer = None

        self.default_theme = create_theme_imgui_default()
        self.__set_theme(None, "Default")
        self.dark_theme = None
        self.light_theme = None

        self.ui_settings_file = general_manager.settings_manager.settings_folder / "ui.json"
        if self.ui_settings_file.exists():
            with self.ui_settings_file.open('r') as fp:
                try:
                    settings: dict = json.load(fp)
                except:
                    settings = {}
                theme = settings.get("theme", "Default")
                self.__set_theme(self, theme)
                dpg.set_value(self.theme_radio, theme)

    def __load_start_window(self):
        self.general_manager.load_main_window()

    def __discover_ports(self):
        self.device_manager.discover_devices()

    def __set_theme(self, sender, app_data):
        if app_data == "Default":
            dpg.bind_theme(self.default_theme)
        elif app_data == "Dark":
            if self.dark_theme is None:
                self.dark_theme = create_theme_imgui_dark()
            dpg.bind_theme(self.dark_theme)
        elif app_data == "Light":
            if self.light_theme is None:
                self.light_theme = create_theme_imgui_light()
            dpg.bind_theme(self.light_theme)

    def cleanup(self):
        with self.ui_settings_file.open('w') as fp:
            json.dump({"theme": dpg.get_value(self.theme_radio)}, fp)

#For some reason the callback for cancellation can't be a class func.
#This is just here to silence the exception of it not being assigned anyways
def explorer_closed(sender, app_data, user_data):
    pass
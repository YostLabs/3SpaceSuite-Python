import sys
from pathlib import Path
sys.path.append(Path(__file__).parent.parent.parent.as_posix())

import dearpygui.dearpygui as dpg
from yostlabs.tss3 import ThreespaceSensor

dpg.create_context()
dpg.create_viewport()

from gui.setting_gui.setting_structures import DpgSettingMenu
from gui.setting_gui.setting_structures_custom import *  #Simply loading this causes the custom types to be registered in the setting menu

sensor = ThreespaceSensor()
setting_menu = DpgSettingMenu(sensor)
setting_menu.create_hierarchy()
with dpg.window() as primary_window:
    with dpg.group(horizontal=True):
        dpg.add_text("Settings Menu", color=(120, 170, 255))
        validate_button = dpg.add_button(label="Validate All", callback=lambda: setting_menu.validate_all())
        apply_button = dpg.add_button(label="Apply All", callback=lambda: setting_menu.apply_all())
    setting_menu.create_gui()

dpg.set_primary_window(primary_window, True)

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
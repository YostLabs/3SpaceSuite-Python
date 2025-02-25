from resource_manager import *

import PIL.Image
import dearpygui.dearpygui as dpg
from dpg_ext.staged_view import StagedView
import dpg_ext.extension_functions as dpg_ext
import PIL
import numpy as np
import time

class DefaultWindow(StagedView):

    ICON_WIDTH = 400

    def __init__(self):
        self.icon_image = PIL.Image.open(IMAGE_FOLDER / "icon_256.png").convert("RGBA")
        texture_data_icon = np.asarray(self.icon_image, dtype=np.float32) #Change to 32 bit floats
        texture_data_icon = np.true_divide(texture_data_icon, 255.0) #Normalize

        self.text_image = PIL.Image.open(IMAGE_FOLDER / "logo.png").convert("RGBA")
        self.text_image = self.text_image.crop((self.ICON_WIDTH + 38, 0, self.text_image.width, self.text_image.height))
        texture_data_text = np.asarray(self.text_image, dtype=np.float32)
        texture_data_text = np.true_divide(texture_data_text, 255.0)
        with dpg.texture_registry(label="DefaultLogoRegistry") as self.logo_registry:
            self.static_logo_texture = dpg.add_static_texture(self.text_image.width, self.text_image.height, texture_data_text)
            self.icon_texture = dpg.add_raw_texture(self.icon_image.width, self.icon_image.height, texture_data_icon, format=dpg.mvFormat_Float_rgba)

        self.icon_angle = 0
        self.last_update_time = 0
        self.speed = -360 * 0.3 #Degrees per seconds

        display_height = 100
        text_ratio = self.text_image.width / self.text_image.height
        text_display_width = int(display_height * text_ratio)
        with dpg.stage(label="Default Window Stage") as self._stage_id:
            with dpg.child_window(border=False):
                with dpg.group(horizontal=True):
                    self.circle_logo = dpg.add_image(self.icon_texture, width=display_height, height=display_height)
                    dpg.add_image(self.static_logo_texture, width=text_display_width, height=display_height)
                dpg.add_text("Resources:")
                with dpg.group(indent=8):
                    dpg_ext.add_hyperlink("Website", "https://yostlabs.com/")
                    dpg_ext.add_hyperlink("3-Space API", "https://github.com/YostLabs/3SpacePythonPackage")
                    dpg_ext.add_hyperlink("Suite Source", "https://github.com/YostLabs/3SpaceSuite-Python")
                    #dpg_ext.add_hyperlink("User Manual", "https://yostlabs.com/wp-content/uploads/pdf/3-Space-Sensor-Users-Manual-3.pdf")

        with dpg.item_handler_registry() as self.visible_handler:
            dpg.add_item_visible_handler(callback=self.__on_visible)
        dpg.bind_item_handler_registry(self.circle_logo, self.visible_handler)

    def __on_visible(self):
        cur_time = time.time()
        elapsed_time = cur_time - self.last_update_time
        self.last_update_time = cur_time

        self.icon_angle = (self.icon_angle + self.speed * elapsed_time) % 360
        
        data = np.asarray(self.icon_image.rotate(self.icon_angle), dtype=np.float32) #Change to 32 bit floats
        texture_data = np.true_divide(data, 255.0) #Normalize
        dpg.set_value(self.icon_texture, texture_data)

    def delete(self):
        dpg.delete_item(self.visible_handler)
        super().delete()

VERSION = None
def createAboutWindow():
    global VERSION
    if VERSION is None:
        try:
            with open(RESOURCE_FOLDER / "version.txt", 'r') as fp:
                VERSION = fp.read()
        except:
            VERSION = "Unknown Version"

    def onWindowClose():
        nonlocal window
        dpg.delete_item(window)

    with dpg.window(label="About", width=500, height=400, modal=True, no_collapse=True, on_close=onWindowClose) as window:
        with dpg.table(header_row=False):
            dpg.add_table_column()
            dpg.add_table_column(width_fixed=True)
            dpg.add_table_column()
            with dpg.table_row():
                dpg.add_table_cell()
                dpg.add_text(VERSION)
                dpg.add_table_cell()
        dpg.add_text("Developers:")
        with dpg.group(indent=8):
            dpg.add_text("Andy Riedlinger")

        dpg.add_separator()
        dpg.add_text("Third Party Resources:")
        with dpg.group(indent=8):
            dpg_ext.add_hyperlink("DearPyGui", "https://github.com/hoffstadt/DearPyGui")
            dpg_ext.add_hyperlink("DearPyGui-Grid", "https://github.com/Atlamillias/dearpygui-grid")
            dpg_ext.add_hyperlink("DearPyGui-FileDialog", "https://github.com/totallynotdrait/file_dialog")
        with dpg.group(horizontal=True):
            dpg.add_text("Icons by")
            dpg_ext.add_hyperlink("Icons8", "https://icons8.com/")
    dpg.render_dearpygui_frame()
    dpg_ext.center_window(window)


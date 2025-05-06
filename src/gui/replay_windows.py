"""
Windows used for the replay tabs
"""
import dearpygui.dearpygui as dpg
import dpg_ext.extension_functions as dpg_ext
import third_party.dearpygui_grid as dpg_grid

from gui.core_ui import StagedView
from gui.orientation_view import OrientationView
from gui.streaming_menu import StreamingOptionSelectionMenu

import gui.resources.obj_lib as obj_lib
import gui.resources.theme_lib as theme_lib

from yostlabs.math.vector import parse_axis_string_info
from utility import MainLoopEventQueue

class OrientationReplayWindow(StagedView):

    TEXTURE_WIDTH = 1200
    TEXTURE_HEIGHT = 800

    def __init__(self):
        self.render_queued = False

        self.playback_time_based = True
        self.playback_speed = 1

        with dpg.stage() as self._stage_id:
            with dpg.child_window(width=-1, height=-1) as self.child_window:
                self.grid = dpg_grid.Grid(1, 2, dpg.last_container(), rect_getter=dpg_ext.get_global_rect)
                self.grid.rows[1].configure(size=56)
                self.grid.offsets = 8, 8, 8, 8

                self.orientation_viewer = OrientationView(obj_lib.getObjFromSerialNumber(None), self.TEXTURE_WIDTH, self.TEXTURE_HEIGHT)
                self.grid.push(self.orientation_viewer.image, 0, 0)
                with dpg.child_window(border=False) as self.timeline_window:
                    dpg.add_spacer()
                    with dpg.group(horizontal=True):
                        #Which drag gets used will be based on whether the loaded data has timestamps in it or not
                        self.playback_time_drag = dpg.add_drag_float(label="Playback Speed", format="%0.01fx", width=80, 
                                                                     default_value=self.playback_speed, speed=0.01, 
                                                                     max_value=16, min_value=0.1, show=self.playback_time_based)
                        self.playback_hz_drag = dpg.add_drag_int(label="Playback Speed", format="%d Hz", width=100, 
                                                                 min_value=1, max_value=2000*16,
                                                                 show=not self.playback_time_based, speed=0.05, default_value=200)
                        dpg.add_child_window(border=False, width=-115, height=1)
                        dpg.add_button(label="Pause")
                        dpg.add_button(label="Play")
                    self.timeline_slider = dpg.add_slider_int(width=-1, format="%d/0", max_value=0, min_value=0, clamped=True, default_value=0)
                    dpg.bind_item_theme(self.timeline_slider, theme_lib.round_theme)
                self.grid.push(self.timeline_window, 0, 1)
            
        with dpg.item_handler_registry() as self.visible_handler:
            dpg.add_item_visible_handler(callback=self.__on_visible)
            dpg.add_item_resize_handler(callback=self.__on_resize)
        dpg.bind_item_handler_registry(self.orientation_viewer.image, self.visible_handler)
    
    def render_image(self):
        self.orientation_viewer.render_image([0, 0, 0, 1], parse_axis_string_info("xyz"))

    def queue_render(self):
        if self.render_queued: return
        self.render_queued = True
        MainLoopEventQueue.queue_sync_event(self.__render_image_queue)

    def __render_image_queue(self):
        self.render_queued = False
        self.render_image()

    def notify_opened(self):
        MainLoopEventQueue.queue_sync_event(self.render_image)

    def __on_visible(self, sender, app_data):
        self.grid()
        self.orientation_viewer.update_image()

    def __on_resize(self, sender, app_data):
        self.queue_render()

    def delete(self):
        dpg.delete_item(self.visible_handler)
        self.grid.clear()
        self.orientation_viewer.delete()
        return super().delete()
    
class ReplayConfigWindow(StagedView):

    def __init__(self):

        with dpg.stage() as self._stage_id:
            with dpg.child_window():
                dpg.add_text("File Loading:")
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Load from Folder")
                    dpg.add_button(label="Load settings from file")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(hint="Data File")
                    dpg.add_button(label="Select")
                dpg.add_spacer(height=20)
                dpg.add_button(label="Load Data")

                dpg.add_separator()
                dpg.add_text("Loaded Settings:")
                
                with dpg.tree_node(label="Header", default_open=True):
                    with dpg.group(): #The sole purpose of this group is for the indent
                        with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False, borders_outerH=False, borders_outerV=False):
                            dpg.add_table_column()
                            dpg.add_table_column()
                            dpg.add_table_column()
                            with dpg.table_row():
                                dpg.add_checkbox(label="Status")
                                dpg.add_checkbox(label="Timestamp")
                                dpg.add_checkbox(label="Echo")
                            with dpg.table_row():
                                dpg.add_checkbox(label="Checksum")
                                dpg.add_checkbox(label="Serial#")
                                dpg.add_checkbox(label="Length")
                with dpg.tree_node(label="Orientation", default_open=True):
                    dpg.add_input_text(label="Axis Order", default_value="XYZ", width=200)
                    dpg.add_combo(["DL", "MDI"], label="Model", width=200, default_value="DL")
                
                with dpg.tree_node(label="Data Gathering", default_open=True):
                    dpg.add_input_float(label="Hz", width=200, default_value=200)
                    dpg.add_text("Slots:")
                    self.stream_slots_menu = StreamingOptionSelectionMenu(None)

                
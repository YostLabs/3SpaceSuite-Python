"""
Windows used for the replay tabs
"""
import dearpygui.dearpygui as dpg
import dpg_ext.extension_functions as dpg_ext
import third_party.dearpygui_grid as dpg_grid
from third_party.file_dialog.fdialog import FileDialog

from gui.core_ui import StagedView
from gui.orientation_view import OrientationView
from gui.streaming_menu import StreamingOptionSelectionMenu

from graphics.objloader import OBJ
import gui.resources.obj_lib as obj_lib
import gui.resources.theme_lib as theme_lib

from yostlabs.math.vector import parse_axis_string_info
from yostlabs.tss3.api import StreamableCommands
from utility import MainLoopEventQueue, Logger

from data_file import TssDataFile, TssDataFileSettings, validate_axis_order, ThreespaceStreamingOption
from data_log.log_settings import LogSettings

from pathlib import Path
import time
import math

import threading

TARED_ORIENTATION_SOURCE = ThreespaceStreamingOption(StreamableCommands.GetTaredOrientation, None)
UNTARED_ORIENTATION_SOURCE = ThreespaceStreamingOption(StreamableCommands.GetUntaredOrientation, None)

GET_TIMESTAMP_OPTION = ThreespaceStreamingOption(StreamableCommands.GetTimestamp, None)

from typing import NamedTuple, Callable
PlaybackGroup = NamedTuple("PlaybackGroup", [("slider", int), ("drag", int)])

def seconds_to_display_time(seconds: float):
    base_seconds = seconds
    minutes, seconds = divmod(seconds, 60)
    minutes = int(minutes)
    hours, minutes = divmod(minutes, 60)
    
    if base_seconds > 3600:
        return f"{hours}:{minutes:02}:{seconds:05.2f}"
    elif base_seconds > 60:
        return f"{minutes}:{seconds:05.2f}"
    else:
        return f"{seconds:.2f}"

class Timeline:

    def __init__(self, slider_callback: Callable[[int, int],None], time_format: Callable[[float],None] = None):
        self.time_based = True
        self.slider_callback = slider_callback
        self.time_format = time_format

        #Auto play control
        self.auto_play = False
        self.auto_play_elapsed_time = 0
        self.last_auto_play_update_time = 0

        with dpg.group(horizontal=True):
            #Which drag gets used will be based on whether the loaded data has timestamps in it or not
            self.playback_time_drag = dpg.add_drag_float(label="Playback Speed", format="%0.01fx", width=80, 
                                                            default_value=1, speed=0.01, 
                                                            max_value=16, min_value=0.1, show=self.time_based)
            self.playback_hz_drag = dpg.add_drag_int(label="Playback Speed", format="%d Hz", width=100, 
                                                        min_value=1, max_value=2000*16,
                                                        show=not self.time_based, speed=0.05, default_value=200)
            dpg.add_child_window(border=False, width=-115, height=1)
            dpg.add_button(label="Pause", callback=self.stop_autoplay)
            dpg.add_button(label="Play", callback=self.start_autoplay)
        self.timeline_slider_hz = dpg.add_slider_int(width=-1, format="%d / 0", max_value=0, min_value=0, clamped=True, 
                                                     default_value=0, callback=self.__hz_slider_callback, show=not self.time_based)
        self.timeline_slider_time = dpg.add_slider_float(width=-1, format="%.0f / 0", max_value=0, min_value=0, clamped=True, 
                                                         default_value=0, callback=self.__time_slider_callback, show=self.time_based)
        dpg.bind_item_theme(self.timeline_slider_hz, theme_lib.round_theme)
        dpg.bind_item_theme(self.timeline_slider_time, theme_lib.round_theme)

        self.__time_group = PlaybackGroup(self.timeline_slider_time, self.playback_time_drag)
        self.__hz_group = PlaybackGroup(self.timeline_slider_hz, self.playback_hz_drag)
        self.__active_group = self.__time_group if self.time_based else self.__hz_group
        self.__inactive_group = self.__time_group if not self.time_based else self.__hz_group

        self.max_value = 0
        self.max_string = ""
    
    def configure(self, time_based: bool, min_value: float|int, max_value: float|int, step=None, callback: Callable[[int, int],None] = None):
        self.time_based = time_based
        if time_based:
            self.__active_group = self.__time_group
            self.__inactive_group = self.__hz_group
        else:
            self.__active_group = self.__hz_group
            self.__inactive_group = self.__time_group
        
        dpg.show_item(self.__active_group.slider)
        dpg.show_item(self.__active_group.drag)
        dpg.hide_item(self.__inactive_group.slider)
        dpg.hide_item(self.__inactive_group.drag)

        self.max_value = max_value
        if self.__active_group is self.__time_group:
            if self.time_format is not None:
                #This is done because for some reason settings the format to a float with a limited number of decimal places also sets the step of the slider
                self.max_string = self.time_format(max_value)
                form = f"{self.time_format(0)} / {self.max_string}"
            else:
                self.max_string = f"{max_value:.3f}"
                form = f"%.3f / {self.max_string}"
        else:
            self.max_string = str(max_value)
            form = f"%d / {self.max_string}"
        dpg.configure_item(self.__active_group.slider, min_value=min_value, max_value=max_value, format=form)

        if callback is not None:
            self.slider_callback = callback

    def set_timeline_value(self, value: int|float):
        self.set_timeline_value_no_callback(value)
        self.slider_callback(None, value)
    
    def set_timeline_value_no_callback(self, value: int|float):
        dpg.set_value(self.__active_group.slider, value)
        self.__set_time_string(value)

    def set_playback_speed(self, value: int|float):
        dpg.set_value(self.__active_group.drag, value)

    def __hz_slider_callback(self, sender, app_data):
        self.slider_callback(sender, app_data)

    def __time_slider_callback(self, sender, app_data):
        self.__set_time_string(app_data)
        self.slider_callback(sender, app_data)

    def __set_time_string(self, value):
        if self.time_format is None: return
        dpg.configure_item(self.timeline_slider_time, format=f"{self.time_format(value)} / {self.max_string}")

    def start_autoplay(self):
        self.auto_play = True
        self.auto_play_elapsed_time = 0
        self.last_auto_play_update_time = time.perf_counter()

    def stop_autoplay(self):
        self.auto_play = False
        self.auto_play_elapsed_time = 0
        self.last_auto_play_update_time = 0

    def autoplay_update(self):
        if not self.auto_play: return

        cur_time = time.perf_counter()
        elapsed_time = cur_time - self.last_auto_play_update_time
        if self.time_based:
            rate = dpg.get_value(self.playback_time_drag)
            new_time = dpg.get_value(self.timeline_slider_time) + (elapsed_time * rate)
            new_time = min(new_time, self.max_value)
            self.set_timeline_value(new_time)
            if new_time == self.max_value:
                self.stop_autoplay()
                return
        else:
            self.auto_play_elapsed_time += elapsed_time
            rate = dpg.get_value(self.playback_hz_drag)
            advance = self.auto_play_elapsed_time * rate
            old_index = dpg.get_value(self.timeline_slider_hz)
            new_index = old_index + math.trunc(advance)
            new_index = min(new_index, self.max_value)
            if old_index != new_index:
                self.set_timeline_value(new_index)
                if new_index == self.max_value:
                    self.stop_autoplay()
                    return

            #Get the left over time
            remainder = (advance - math.trunc(advance)) / rate
            self.auto_play_elapsed_time = remainder

        self.last_auto_play_update_time = cur_time

class OrientationReplayWindow(StagedView):

    TEXTURE_WIDTH = 1200
    TEXTURE_HEIGHT = 800

    def __init__(self):
        self.render_queued = False

        self.orientation_source: ThreespaceStreamingOption = None

        self.data_file: TssDataFile = None
        self.quat = [0, 0, 0, 1]
        self.axis_info = parse_axis_string_info("xyz")

        with dpg.stage() as self._stage_id:
            with dpg.child_window(width=-1, height=-1) as self.child_window:
                self.grid = dpg_grid.Grid(1, 2, dpg.last_container(), rect_getter=dpg_ext.get_global_rect)
                self.grid.rows[1].configure(size=56)
                self.grid.offsets = 8, 8, 8, 8

                self.orientation_viewer = OrientationView(obj_lib.getObjFromSerialNumber(None), self.TEXTURE_WIDTH, self.TEXTURE_HEIGHT)
                self.grid.push(self.orientation_viewer.image, 0, 0)
                with dpg.child_window(border=False) as self.timeline_window:
                    dpg.add_spacer()
                    self.timeline = Timeline(lambda s, a: None, time_format=seconds_to_display_time)
                self.grid.push(self.timeline_window, 0, 1)
            
        with dpg.item_handler_registry() as self.visible_handler:
            dpg.add_item_visible_handler(callback=self.__on_visible)
            dpg.add_item_resize_handler(callback=self.__on_resize)
        dpg.bind_item_handler_registry(self.orientation_viewer.image, self.visible_handler)

        self.timeline.configure(True, 0, 0)

    #Handles updating the slider as well
    def render_index(self, index: int):
        """
        Does NOT update the slider as well if called programatically
        """
        if self.data_file is None or self.orientation_source is None: return
        self.quat = self.data_file.get_value(index, self.orientation_source)
        self.queue_render()

    def set_default(self):
        """
        Must be called from main thread
        """
        self.timeline.stop_autoplay()
        self.timeline.configure(True, 0, 0)
        self.timeline.set_timeline_value(0)
        self.quat = [0, 0, 0, 1]
        self.axis_info = parse_axis_string_info("xyz")
        self.queue_render()

    def set_data_file(self, data_file: TssDataFile):
        """
        Must be called from main thread
        """
        self.set_default()
        self.data_file = data_file
        if len(data_file) == 0: return

        if TARED_ORIENTATION_SOURCE in data_file.settings.stream_slots:
            self.orientation_source = TARED_ORIENTATION_SOURCE
        elif UNTARED_ORIENTATION_SOURCE in data_file.settings.stream_slots:
            self.orientation_source = UNTARED_ORIENTATION_SOURCE
        else:
            self.orientation_source = None
            return

        self.axis_info = self.data_file.settings.axis_order_info

        #Set the time source and load the initial position
        if data_file.has_monotime:
            self.timeline.configure(True, min_value=0, max_value=data_file.get_monotime(-1), callback=self.__timeline_callback_time)
            self.timeline.set_timeline_value(0)            
            self.timeline.set_playback_speed(1)
        else:
            self.timeline.configure(False, min_value=1, max_value=len(data_file), callback=self.__timeline_callback_hz)
            self.timeline.set_timeline_value(1)
            self.timeline.set_playback_speed(data_file.settings.data_hz)
    
    def set_model(self, model: OBJ):
        self.orientation_viewer.set_model(model)

    #This should almost always be used over render_image
    def queue_render(self):
        if self.render_queued: return
        self.render_queued = True
        MainLoopEventQueue.queue_sync_event(self.__render_image_queue)

    def render_image(self):
        self.orientation_viewer.render_image(self.quat, self.axis_info)

    def __render_image_queue(self):
        self.render_queued = False
        self.render_image()

    def __timeline_callback_hz(self, sender, value: int):
        self.render_index(value-1)

    def __timeline_callback_time(self, sender, time: float):
        self.render_index(self.data_file.monotime_to_index(time))

    def notify_opened(self):
        MainLoopEventQueue.queue_sync_event(self.render_image)

    def __on_visible(self, sender, app_data):
        self.grid()
        self.orientation_viewer.update_image()
        self.timeline.autoplay_update()

    def __on_resize(self, sender, app_data):
        self.queue_render()

    def delete(self):
        dpg.delete_item(self.visible_handler)
        self.grid.clear()
        self.orientation_viewer.delete()
        return super().delete()
    
def load_data_file_thread(data_file: TssDataFile, return_list: list):
    try:
        data_file.load_data()
    except Exception as e:
        return_list.append(e)
        return

    #Insert Monotonic Time data if time is included. This is to avoid having to source time from different
    #sources, as well as to handle any wrapping. If the user set the timestamp back to 0 during the data gathering,
    #well things are going to get awkward then.
    data_file.compute_monotime(divider=1_000_000, start_at_zero=True)

class ReplayConfigWindow(StagedView):

    VALID_DATA_FILE_EXTENSIONS = (".csv", ".bin")

    def __init__(self, orient_window: OrientationReplayWindow, log_settings: LogSettings):
        self.log_settings = log_settings #Used for the default directory to load when file exploring
        self.orient_window = orient_window

        with dpg.stage() as self._stage_id:
            with dpg.child_window():
                dpg.add_text("File Loading:")
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Load from Folder", callback=self.__start_folder_select)
                    dpg.add_button(label="Load settings from file", callback=self.__start_config_file_select)
                with dpg.group(horizontal=True):
                    self.data_file_input = dpg.add_input_text(hint="Data File", width=-80)
                    dpg.add_button(label="Select", callback=self.__start_data_file_select)
                dpg.add_spacer(height=20)
                dpg.add_button(label="Load Data", callback=self.load_data)

                dpg.add_separator()
                dpg.add_text("Loaded Settings:")
                
                with dpg.tree_node(label="Header", default_open=True):
                    with dpg.group(): #The sole purpose of this group is for the indent
                        with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False, borders_outerH=False, borders_outerV=False):
                            dpg.add_table_column()
                            dpg.add_table_column()
                            dpg.add_table_column()
                            with dpg.table_row():
                                self.status_box = dpg.add_checkbox(label="Status")
                                self.timestamp_box = dpg.add_checkbox(label="Timestamp")
                                self.echo_box = dpg.add_checkbox(label="Echo")
                            with dpg.table_row():
                                self.checksum_box = dpg.add_checkbox(label="Checksum")
                                self.serial_box = dpg.add_checkbox(label="Serial#")
                                self.length_box = dpg.add_checkbox(label="Length")
                with dpg.tree_node(label="Orientation", default_open=True):
                    self.axis_order_input = dpg.add_input_text(label="Axis Order", width=200)
                    self.model_combo = dpg.add_combo(obj_lib.getAvailableModelNames(), label="Model", width=200)
                
                with dpg.tree_node(label="Data Gathering", default_open=True):
                    self.data_hz_input = dpg.add_input_float(label="Hz", width=200)
                    dpg.add_text("Slots:")
                    self.stream_slots_menu = StreamingOptionSelectionMenu(None)
        
        with dpg.item_handler_registry() as self.edited_handler:
            dpg.add_item_deactivated_after_edit_handler(callback=self.__axis_order_edited)
        dpg.bind_item_handler_registry(self.axis_order_input, self.edited_handler)

        self.default_settings()

    def default_settings(self):
        dpg.set_value(self.status_box, False)
        dpg.set_value(self.timestamp_box, False)
        dpg.set_value(self.echo_box, False)
        dpg.set_value(self.checksum_box, False)
        dpg.set_value(self.serial_box, False)
        dpg.set_value(self.length_box, False)

        self.set_axis_order("XYZ")

        modelnames = obj_lib.getAvailableModelNames()
        default_model = obj_lib.getDefaultModelName()
        if default_model not in modelnames:
            default_model = modelnames[0]
        dpg.set_value(self.model_combo, default_model)

        dpg.set_value(self.data_hz_input, 200)
        self.stream_slots_menu.overwrite_options([])

    def load_config_file(self, path: Path):
        self.default_settings() #Set settings back to default so if an error occurs, defaults are set

        try:
            #Note: This loads as much data as it can. Anything not available gets set to None.
            settings = TssDataFileSettings.from_config_file(path)
        except Exception as e:
            Logger.log_error(f"Failed to load config file {path} with error {e}")
            dpg.render_dearpygui_frame() #Required to allow the modal file explorer to close so the modal popup can show
            dpg_ext.create_popup_message(f"Failed to load settings from {path.as_posix()}", title="Error", width=400)
            return
        
        errors = self.set_settings_from_obj(settings)
        if len(errors) > 0:
            message = "Failed to load the following settings:\n"
            for error in errors:
                message += f"  {error}\n"
            message += "\nPlease enter them manually or load a different file."
            dpg.render_dearpygui_frame() #Required to allow the modal file explorer to close so the modal popup can show
            dpg_ext.create_popup_message(message, title="Error", width=400)
            print(message)

    def load_data(self):
        data_path = dpg.get_value(self.data_file_input)
        data_path = Path(data_path)
        if not data_path.exists() or data_path.suffix not in self.VALID_DATA_FILE_EXTENSIONS:
            dpg_ext.create_popup_message("Invalid data path supplied.", title="Error")
            return
    
        settings = self.get_settings()
        if settings is None:          
            dpg_ext.create_popup_message("Invalid settings supplied.", title="Error")
            return
        
        data_file = TssDataFile(data_path, settings)
        popup = dpg_ext.create_popup_circle_loading_indicator(title="Loading data...")

        output = []
        thread = threading.Thread(target=load_data_file_thread, args=(data_file, output), daemon=True)
        thread.start()
        while thread.is_alive():
            dpg.render_dearpygui_frame()
        thread.join() #Should finish instantly

        if len(output) > 0:
            popup.set_message_box(f"Failed to load data\n{output[0]}", title="Error")
            return
    
        if len(data_file) == 0:
            popup.set_message_box(f"No data loaded. Check for accurate config settings.", title="Error")       
            return

        self.orient_window.set_data_file(data_file)
        self.orient_window.set_model(obj_lib.getObjFromName(dpg.get_value(self.model_combo)))
        
        popup.set_message_box(f"Finished loading file.", title="Done")

    def set_settings_from_obj(self, settings: TssDataFileSettings):
        #Set all possible settings based on the loaded settings
        errors = []
        if settings.header is None:
            errors.append("Header")
        else:
            dpg.set_value(self.status_box, settings.header.status_enabled)
            dpg.set_value(self.timestamp_box, settings.header.timestamp_enabled)
            dpg.set_value(self.echo_box, settings.header.echo_enabled)
            dpg.set_value(self.checksum_box, settings.header.checksum_enabled)
            dpg.set_value(self.serial_box, settings.header.serial_enabled)
            dpg.set_value(self.length_box, settings.header.length_enabled)
        
        if settings.axis_order is None:
            errors.append("Axis Order")
        else:
            dpg.set_value(self.axis_order_input, settings.axis_order)
        
        if settings.serial_no is None:
            errors.append("Model")
        else:
            name = obj_lib.getModelNameFromSerialNumber(settings.serial_no)
            dpg.set_value(self.model_combo, name)
        
        if settings.data_hz is None:
            errors.append("Data Hz")
        else:
            dpg.set_value(self.data_hz_input, settings.data_hz)
        
        if settings.stream_slots is None:
            errors.append("Stream Slots")
        else:
            self.stream_slots_menu.overwrite_options(settings.stream_slots)
        
        return errors

    def get_settings(self):
        settings = TssDataFileSettings()

        #Header
        settings.header.status_enabled = dpg.get_value(self.status_box)
        settings.header.timestamp_enabled = dpg.get_value(self.timestamp_box)
        settings.header.echo_enabled = dpg.get_value(self.echo_box)
        settings.header.checksum_enabled = dpg.get_value(self.checksum_box)
        settings.header.serial_enabled = dpg.get_value(self.serial_box)
        settings.header.length_enabled = dpg.get_value(self.length_box)

        #Axis Order
        axis_order = dpg.get_value(self.axis_order_input)
        #This shouldn't be required because the edited handler ensures the value is always valid
        if not validate_axis_order(axis_order):
            return None
        
        settings.axis_order = axis_order
        settings.update_axis_cache()

        settings.data_hz = dpg.get_value(self.data_hz_input)
        settings.stream_slots = self.stream_slots_menu.get_options()

        return settings

    def __start_data_file_select(self, sender, app_data):
        def on_close():
            nonlocal selector
            selector.destroy()

        def on_select(selections):
            on_close()
            if len(selections) == 0:
                return
            path = Path(selections[0][1])
            dpg.set_value(self.data_file_input, path.as_posix()) 
        
        default_path = self.log_settings.output_directory
        filter_list = ['/'.join(self.VALID_DATA_FILE_EXTENSIONS)]
        filter_list.extend(self.VALID_DATA_FILE_EXTENSIONS)
        selector = FileDialog(title="Data File Selector", width=900, height=550, min_size=(700,400), files_only=True,
                                            multi_selection=False, modal=True, on_select=on_select, on_cancel=on_close,
                                            default_path=default_path.as_posix(), filter_list=filter_list, file_filter=filter_list[0], no_resize=False)        
        selector.show_file_dialog()

    def __start_config_file_select(self, sender, app_data):
        def on_close():
            nonlocal selector
            selector.destroy()

        def on_select(selections):
            on_close()
            if len(selections) == 0:
                return

            self.load_config_file(Path(selections[0][1]))         
        
        default_path = self.log_settings.output_directory
        selector = FileDialog(title="Config File Selector", width=900, height=550, min_size=(700,400), files_only=True,
                                            multi_selection=False, modal=True, on_select=on_select, on_cancel=on_close,
                                            default_path=default_path.as_posix(), filter_list=[".cfg"], file_filter=".cfg", no_resize=False)        
        selector.show_file_dialog()

    def __find_data_and_config(self, folder: Path):
        data_file = None
        config_file = None
        subfolders = []
        for file in folder.iterdir():
            if file.suffix in self.VALID_DATA_FILE_EXTENSIONS:
                data_file = file
            elif file.suffix == ".cfg":
                config_file = file
            
            if file.is_dir():
                subfolders.append(file)

            if data_file != None and config_file != None:
                break
        
        return data_file, config_file, subfolders

    def __start_folder_select(self, sender, app_data):
        def on_close():
            nonlocal selector
            selector.destroy()

        def on_select(selections):
            on_close()
            if len(selections) == 0:
                return
            
            folder = Path(selections[0][1])
            
            #Recurse into subfolders if only 1 to allow easily loading based off timestamps if only one device logged.
            #If more then one device logged, this will instead error as the user would need to select the device            
            recurse_count = 0 #Prevent infinite loops
            data_file, config_file, subfolders = self.__find_data_and_config(folder)
            while data_file is None and config_file is None and len(subfolders) == 1 and recurse_count < 5:
                folder = subfolders[0]
                data_file, config_file, subfolders = self.__find_data_and_config(folder)

            if data_file is not None:
                dpg.set_value(self.data_file_input, data_file.as_posix())
            
            if config_file is not None:
                self.load_config_file(config_file)
        
        default_path = self.log_settings.output_directory
        selector = FileDialog(title="Data Folder Selector", width=900, height=550, min_size=(700,400), dirs_only=True,
                                            multi_selection=False, modal=True, on_select=on_select, on_cancel=on_close,
                                            default_path=default_path.as_posix(), no_resize=False)        
        selector.show_file_dialog()

    def set_axis_order(self, order: str):
        if not validate_axis_order(order):
            return
        dpg.set_value(self.axis_order_input, order)
        self.axis_order = order

    def __axis_order_edited(self, sender, app_data, user_data):
        new_order = dpg.get_value(app_data)
        if not validate_axis_order(new_order):
            self.set_axis_order(self.axis_order)
        else:
            self.axis_order = new_order

    def delete(self):
        dpg.delete_item(self.edited_handler)
        self.stream_slots_menu.delete()
        return super().delete()
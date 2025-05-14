"""
Windows Specific to the Logger/General Tab
"""
import dearpygui.dearpygui as dpg
from dpg_ext.global_lock import dpg_lock

from dpg_ext.staged_view import StagedView, StagedTabManager
from dpg_ext.selectable_button import SelectableButton
from dpg_ext.dynamic_button import DynamicButton
from dpg_ext.filtered_dropdown import FilteredDropdown
from dpg_ext.log_window import LogWindow
from third_party.file_dialog.fdialog import FileDialog

from gui.core_ui import FontManager
import gui.resources.theme_lib as theme_lib

from managers.device_managers import DeviceManager, ThreespaceDevice

from dataclasses import dataclass
from utility import Logger, MainLoopEventQueue
import pathlib
from managers.resource_manager import *

from devices import StreamableCommands, ThreespaceStreamingOption
from data_log.log_settings import LogSettings
from gui.streaming_menu import StreamingOptionSelectionMenu

class LoggerBanner(SelectableButton): ...

from data_log.log_data import DataLogger
from gui.replay_windows import OrientationReplayWindow, DataChartReplayWindow, ReplayConfigWindow

class LoggerMasterWindow(StagedTabManager):

    def __init__(self, device_manager: DeviceManager, data_logger: DataLogger, log_settings: LogSettings):
        super().__init__()
        with dpg.stage(label="Logger Master Stage") as self._stage_id:
            with dpg.tab_bar(label="Logger Tabs"):
                self.set_tab_bar(dpg.top_container_stack())
                with dpg.tab(label="Logging") as self.logging_tab:
                    self.add_tab(DataLogWindow(device_manager, data_logger, log_settings).submit())
                with dpg.tab(label="Log Config"):
                    self.add_tab(DataLogConfigWindow(device_manager, log_settings).submit())
                with dpg.tab(label="Orientation"):
                    self.orient_window = OrientationReplayWindow()
                    self.add_tab(self.orient_window.submit())
                with dpg.tab(label="Data Charts"):
                    self.data_window = DataChartReplayWindow()
                    self.add_tab(self.data_window.submit())
                with dpg.tab(label="Replay Config"):
                    self.add_tab(ReplayConfigWindow(self.orient_window, self.data_window, log_settings).submit())                                        
        
        self.set_open_tab(self.logging_tab)

def start_logging(data_logger: DataLogger, device_manager: DeviceManager, log_settings: LogSettings):
    if data_logger.is_logging():
        return

    groups = []
    for device in device_manager.threespace_manager.get_devices():
        if not device.is_open or device.in_bootloader: continue 
        header = device.build_header_bitfield(success_fail=log_settings.header_status, timestamp=log_settings.header_timestamp, 
                                    echo=log_settings.header_echo, checksum=log_settings.header_checksum, 
                                    serial_number=log_settings.header_serial, data_len=log_settings.header_length)
        stream_options = log_settings.get_slots_for_serial(device.cached_serial_number)
        log_device = ThreeSpaceLogDevice(device, stream_options, header,
                                            log_settings.hz, binary=log_settings.binary_mode,
                                            sync_timestamp=log_settings.synchronize_timestamp)
        groups.append(DefaultLogGroup([log_device], device.name, csv=not log_settings.binary_mode))
    if len(groups) == 0:
        Logger.log_warning("No available log devices connected.")
        return

    data_logger.set_duration(log_settings.duration)
    data_logger.set_log_groups(groups)
    data_logger.set_output_folder(log_settings.output_directory)
    data_logger.start_logging()

def stop_logging(data_logger: DataLogger):
    if not data_logger.is_logging():
        return
    data_logger.stop_logging()

import threading
import time
from data_log.log_data import DataLogger, DefaultLogGroup
from data_log.log_devices import ThreeSpaceLogDevice
class DataLogWindow(StagedView):

    def __init__(self, device_manager: DeviceManager, data_logger: DataLogger, log_settings: LogSettings):
        self.log_settings = log_settings
        self.data_logger = data_logger
        self.device_manager = device_manager
        with dpg.theme(label="Start Button Theme") as self.start_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (29, 148, 172, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (29, 148, 172, 241))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (29, 148, 172, 193))

        with dpg.theme(label="Stop Button Theme") as self.stop_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (255, 104, 37, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 104, 37, 236))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (255, 104, 37, 193))

        with dpg.stage(label="Data Log Window Stage") as self._stage_id:
            with dpg.child_window(autosize_x=True, autosize_y=True, label="DataLogWindow") as self.child_window:
                with dpg.table(header_row=False):
                    dpg.add_table_column(width_stretch=True, init_width_or_weight=0.1)
                    dpg.add_table_column(width_stretch=True, init_width_or_weight=0.4)
                    dpg.add_table_column(width_stretch=True, init_width_or_weight=0.4)
                    dpg.add_table_column(width_stretch=True, init_width_or_weight=0.1)
                    with dpg.table_row():
                        dpg.add_table_cell()
                        self.start_button = dpg.add_button(label="Start Logging", width=-1, height=75, callback=self.start_logging)
                        self.stop_button = dpg.add_button(label="Stop Logging", width=-1, height=75, callback=self.stop_logging)
                        dpg.add_table_cell()
                    dpg.bind_item_theme(self.start_button, self.start_theme)
                    dpg.bind_item_font(self.start_button, FontManager.DEFAULT_FONT_LARGE)
                    dpg.bind_item_theme(self.stop_button, self.stop_theme)
                    dpg.bind_item_font(self.stop_button, FontManager.DEFAULT_FONT_LARGE)

                # with dpg.table(header_row=False):
                #     dpg.add_table_column(width_stretch=True, init_width_or_weight=0.2)
                #     dpg.add_table_column(width_stretch=True, init_width_or_weight=0.6)
                #     dpg.add_table_column(width_stretch=True, init_width_or_weight=0.2)
                #     with dpg.table_row():
                #         dpg.add_table_cell()
                #         self.split_button = dpg.add_button(label="Split", width=-1, height=75, callback=self.split_logs)
                #         dpg.add_table_cell()
                #     dpg.bind_item_font(self.split_button, FontManager.DEFAULT_FONT_LARGE)

                dpg.add_spacer(height=12)
                dpg.add_separator()
                dpg.add_spacer(height=12)

                with dpg.group(horizontal=True):
                    dpg.add_text("Output Folder:")
                    #Folder/File pathname sanitization is sorta a messy thing. So just going to let the file selector do it's work
                    #and make this a readonly display field of the path
                    self.input_directory_text = dpg.add_input_text(default_value=self.log_settings.output_directory.as_posix(),
                                                                   readonly=True)
                    dpg.add_button(label="Select", callback=self.__on_select_button)

                dpg.add_separator()
                with dpg.table(header_row=False):
                    dpg.add_table_column(width_stretch=True, init_width_or_weight=0.3)
                    dpg.add_table_column(width_stretch=True, init_width_or_weight=0.7)
                    with dpg.table_row():
                        with dpg.group(horizontal=True):
                            dpg.add_text("Logger Thread Hertz:")
                            self.fps_text = dpg.add_text(f"0")
                        with dpg.group(horizontal=True):
                            dpg.add_text("Time:")
                            self.time_text = dpg.add_text(f"0.00")
                self.log_window = LogWindow(height=-1, flush_count=100)
                self.log_window.submit(parent=dpg.top_container_stack())

            self.data_logger.on_update.subscribe(self.on_data_logger_update)
            self.data_logger.on_logging_stopped.subscribe(self.on_data_logger_stopped)

        Logger.connect_window(self.log_window)

    def __on_select_button(self, sender, app_data, user_data):
        def on_close():
            nonlocal firmware_selector
            firmware_selector.destroy()

        def on_folder_select(selections):
            on_close()
            if len(selections) == 0:
                return
            path = selections[0][1]
            self.log_settings.output_directory = pathlib.Path(path)
            dpg.set_value(self.input_directory_text, self.log_settings.output_directory.as_posix())            
        
        default_path = PLATFORM_FOLDERS.user_documents_path or APPLICATION_FOLDER
        if self.log_settings.output_directory.exists():
            default_path = self.log_settings.output_directory.parent
        firmware_selector = FileDialog(title="Output Folder Selector", width=900, height=550, min_size=(700,400), dirs_only=True, 
                                            multi_selection=False, modal=True, on_select=on_folder_select, on_cancel=on_close,
                                            default_path=default_path.as_posix(), filter_list=[""], file_filter="", no_resize=False)
        
        firmware_selector.show_file_dialog()

    def start_logging(self):
        start_logging(self.data_logger, self.device_manager, self.log_settings)

    def stop_logging(self):
        stop_logging(self.data_logger)

    def on_data_logger_stopped(self):
        dpg.set_value(self.fps_text, "0")
        dpg.set_value(self.time_text, "0.00")

    def split_logs(self):
        pass
        # if self.data_logger.is_logging():
        #     Logger.log_info(f"{self.data_logger.time_elapsed:.2f}s elapsed, inserting break")

    def on_data_logger_update(self, time_elapsed: float):
        dpg.set_value(self.time_text, f"{time_elapsed:.2f}")
        dpg.set_value(self.fps_text, f"{int(self.data_logger.fps)}")

    def delete(self):
        self.data_logger.on_update.unsubscribe(self.on_data_logger_update)
        self.data_logger.on_logging_stopped.unsubscribe(self.on_data_logger_stopped)
        dpg.delete_item(self.stop_theme)
        dpg.delete_item(self.start_theme)

class DataLogConfigWindow(StagedView):

    def __init__(self, device_manager: DeviceManager, log_settings: LogSettings):
        self.device_manager = device_manager
        self.log_settings = log_settings

        with dpg.stage(label="Data Log Config Stage") as self._stage_id:
            with dpg.child_window(autosize_x=True, autosize_y=True, label="DataLogConfigWindow") as self.window:
                with dpg.group(horizontal=True):
                    dpg.add_text("Header:")
                    dpg.add_text("?", color=theme_lib.color_tooltip)
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text("The Echo, Checksum, and Length header fields are forced on as required by the 3-Space API.", wrap=300)
                with dpg.group(indent=24): #The sole purpose of this group is for the indent
                    with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False, borders_outerH=False, borders_outerV=False):
                        dpg.add_table_column()
                        dpg.add_table_column()
                        dpg.add_table_column()
                        with dpg.table_row():
                            dpg.add_checkbox(label="Status", source=self.log_settings._value_header_status)
                            dpg.add_checkbox(label="Timestamp", source=self.log_settings._value_header_timestamp)
                            dpg.add_checkbox(label="Echo", source=self.log_settings._value_header_echo, enabled=False)
                        with dpg.table_row():
                            dpg.add_checkbox(label="Checksum", source=self.log_settings._value_header_checksum, enabled=False)
                            dpg.add_checkbox(label="Serial#", source=self.log_settings._value_header_serial)
                            dpg.add_checkbox(label="Length", source=self.log_settings._value_header_length, enabled=False)
                with dpg.group(horizontal=True):
                    dpg.add_text("Data Mode:")
                    default_mode = "Binary" if self.log_settings.binary_mode else "Ascii"
                    dpg.add_radio_button(items=["Ascii", "Binary"], callback=self.__mode_radio_callback, horizontal=True, default_value=default_mode)
                    dpg.add_text("?", color=theme_lib.color_tooltip)
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text("When using Ascii mode the Checksum and Length header fields will still be gathered in Binary and so may appear inaccurate.", wrap=300)
                
                with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False, borders_outerH=False, borders_outerV=False):
                    dpg.add_table_column(init_width_or_weight=275, width_fixed=True)
                    dpg.add_table_column()
                    dpg.add_table_column()
                    with dpg.table_row():
                        with dpg.group(horizontal=True):
                            dpg.add_checkbox(label="Synchronize Timestamp", source=self.log_settings._value_synchronize_timestamp)
                            dpg.add_text("?", color=theme_lib.color_tooltip)
                            with dpg.tooltip(dpg.last_item()):
                                dpg.add_text("If selected, timestamps will reset to 0 when logging starts.", wrap=300)
                        dpg.add_input_float(label="HZ", source=self.log_settings._value_log_hz, step=10, min_value=0.001, max_value=2000, max_clamped=True, min_clamped=True)
                        with dpg.group(horizontal=True):
                            #Max value of 1 Week. It can go much higher then that, but capping at that for now since this is meant more as a testing suite
                            #then an incredibly robust logging system that will reliably have no errors for an extremely long period of time.
                            dpg.add_input_float(label="Duration", source=self.log_settings._value_log_duration, step=1, min_value=0, max_value=604800, min_clamped=True, max_clamped=True)
                            dpg.add_text("?", color=theme_lib.color_tooltip)
                            with dpg.tooltip(dpg.last_item()):
                                dpg.add_text("A duration of 0 logs forever")
                dpg.add_spacer()
                dpg.add_separator()
                dpg.add_spacer()
                dpg.add_text("Logging Slot Configuration")
                self.slots_window = LoggingSlotsConfigWindow(device_manager, log_settings).submit()

    def __mode_radio_callback(self, sender, app_data, user_data):
        self.log_settings.binary_mode = app_data == "Binary"

    def notify_opened(self, old_view: StagedView):
        self.slots_window.notify_opened(old_view)

    def delete(self):
        self.slots_window.delete()


class LoggingSlotsConfigWindow(StagedView):

    def __init__(self, device_manager: DeviceManager, log_settings: LogSettings):
        self.device_manager = device_manager
        self.log_settings = log_settings

        self.default_item = "Select a Sensor"
        self.devices = [d for d in self.device_manager.threespace_manager.get_devices() if d.is_open and not d.in_bootloader]
        self.keys = [d.name for d in self.devices]
        self.keys.insert(0, self.default_item)
        self.device_menu: StreamingOptionSelectionMenu = None
        self.loaded_device = None

        with dpg.stage(label="Data Log Slots Stage") as self._stage_id:
            dpg.add_text("General:")
            with dpg.group(indent=24):
                dpg.add_button(label="Apply to all sensors", callback=self.apply_general_settings)
                
                options = self.log_settings.slot_configuration["general"]
                self.general_menu = StreamingOptionSelectionMenu(on_modified_callback=self.__on_slots_modified)
                self.general_menu.overwrite_options(options)

            dpg.add_text("Sensor:")
            with dpg.group(indent=24):
                with dpg.group(horizontal=True):
                    self.dropdown = FilteredDropdown(items=self.keys, default_item=self.default_item, 
                        width=int(200*1.36), allow_custom_options=False, allow_empty=False,
                        callback=self.__on_device_selected).submit()
                    self.apply_to_specific_button = dpg.add_button(label="Apply General", show=False, callback=lambda s, a: self.apply_to_current())
                self.selected_sensor_container = dpg.add_group()


        self.__on_device_selected(None, self.default_item)

    def notify_opened(self, old_view: StagedView):
        #Reload available devices
        self.devices = [d for d in self.device_manager.threespace_manager.get_devices() if d.is_open and not d.in_bootloader]
        self.keys = [d.name for d in self.devices]
        self.keys.insert(0, self.default_item)
        reset = self.loaded_device not in self.devices

        #Update the selection with available devices
        self.dropdown.clear_all_items()
        for key in self.keys:
            self.dropdown.add_item(key)
        
        #Load device to show if the previous device is no longer present
        if reset:
            self.dropdown.set_value(self.default_item)
            self.__on_device_selected(None, self.default_item)

    def __on_device_selected(self, sender, value: str):
        device = None
        if value != self.default_item:
            devices = self.device_manager.threespace_manager.get_devices()
            for d in devices:
                if d.name == value:
                    device = d
                    break
            if device is None:
                Logger.log_error(f"Failed to find device for selection: {value}")
        self.__load_device(device)
    
    def __load_device(self, device: ThreespaceDevice):
        if self.loaded_device == device: return
        self.__clear_device()
        if device is None:
            return
        options = self.log_settings.get_slots_for_serial(device.cached_serial_number)
        dpg.push_container_stack(self.selected_sensor_container)
        self.device_menu = StreamingOptionSelectionMenu(device, on_modified_callback=self.__on_slots_modified)
        dpg.pop_container_stack()
        self.loaded_device = device
        self.device_menu.overwrite_options(options)
        dpg.show_item(self.apply_to_specific_button)

    def __clear_device(self):
        if self.device_menu is not None:
            self.device_menu.delete()
            self.device_menu = None
        dpg.delete_item(self.selected_sensor_container, children_only=True)
        dpg.hide_item(self.apply_to_specific_button)
        self.loaded_device = None

    def __on_slots_modified(self, sender: "StreamingOptionSelectionMenu"):
        options = sender.get_options()
        if sender == self.general_menu:
            self.log_settings.slot_configuration["general"] = options
        else:
            if self.loaded_device is None:
                Logger.log_error("Slots modified but no device loaded.")
                return
            self.log_settings.slot_configuration[self.loaded_device.cached_serial_number] = options
    
    def apply_to_current(self, options: list[ThreespaceStreamingOption] = None):
        if self.device_menu is None: return
        if options is None:
            options = self.general_menu.get_options()
        self.device_menu.overwrite_options(options)

    def apply_general_settings(self):
        options = self.general_menu.get_options()
        self.apply_to_current(options)
        for device in self.devices:
            if not device.is_open or device.in_bootloader: #Shouldn't be, but double checking
                continue
            self.log_settings.slot_configuration[device.cached_serial_number] = options

    def delete(self):
        self.__clear_device()
        self.general_menu.delete()
        self.dropdown.delete()

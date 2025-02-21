import dearpygui.dearpygui as dpg
import dpg_ext.extension_functions as dpg_ext
from dpg_ext.log_window import MultilineText
from dpg_ext.selectable_button import SelectableButton
from dpg_ext.filtered_dropdown import FilteredDropdown
from dpg_ext.staged_view import StagedView
from dpg_ext.global_lock import dpg_lock

from devices import ThreespaceDevice, StreamableCommands, ThreespaceStreamingManager, ThreespaceStreamingStatus, ThreespaceCommandInfo, threespace_consts
from yostlabs.tss3.utils.calibration import ThreespaceGradientDescentCalibration
from utility import Logger, MainLoopEventQueue

from dataclasses import dataclass, field
from typing import Callable

from core_ui import FontManager, DpgWizard
import theme_lib, obj_lib, texture_lib

import math
import numpy as np
from yostlabs.math import quaternion
from yostlabs.math import vector
import pathlib

from resource_manager import *
from macro_manager import MacroManager, MacroConfigurationWindow, TerminalMacro

from gl_renderer import GL_Renderer
from gl_orientation_window import GlOrientationViewer, gl_sensor_to_gl_quat, gl_space_to_sensor_quat
from gl_texture_renderer import TextureRenderer

class SensorBanner(SelectableButton):

    def __init__(self, device: ThreespaceDevice, text = None, selected = False, on_select = None):
        super().__init__(text=text, selected=selected, on_select=on_select, height=50)
        dpg.configure_item(self.button, label=device.name)

        self.device = device
        self.device.subscribe_property_update(self.on_property_changed)
    
    def on_property_changed(self, device: ThreespaceDevice):
        dpg.configure_item(self.button, label=device.name)


class SensorMasterWindow(StagedView):
    """
    The window that contains all the other windows
    that are specific to a sensor. Can also handle
    the construction of all the other windows as well
    """

    DISCONNECT_THEME = None
    INVISIBLE_THEME = None

    def __init__(self, threespace_device: ThreespaceDevice, sensor_banner: SensorBanner, macro_manager: MacroManager):
        if SensorMasterWindow.DISCONNECT_THEME is None:
            with dpg.theme(label="SensorDisconnectTheme") as SensorMasterWindow.DISCONNECT_THEME:
                with dpg.theme_component(dpg.mvTabButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Tab, theme_lib.color_disconnect_red)

            with dpg.theme(label="SensorInvisibleTheme") as SensorMasterWindow.INVISIBLE_THEME:
                with dpg.theme_component(dpg.mvTabButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Tab, (0, 0, 0, 0))
                    dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (0, 0, 0, 0))
                    dpg.add_theme_color(dpg.mvThemeCol_TabActive, (0, 0, 0, 0))                    

        with dpg.stage(label="Sensor Master Stage") as self._stage_id:
            with dpg.child_window(width=-1, height=-1, border=False) as self.child_window: #This way, the visuals can be edited without having to reload the stage
                self.connection_window = SensorConnectionWindow(threespace_device, self.on_sensor_opened)
                self.connection_window.submit()

        #On connection, the actual window will be loaded
        self.staged_view_dict = None

        self.macro_manager = macro_manager
        self.device = threespace_device
        self.deleted = False

    def load_firmware_windows(self):
        dpg.push_container_stack(self.child_window)
        self.staged_view_dict: dict[int,StagedView] = {}
        with dpg.tab_bar(label="Sensor Tabs", callback=self.__tab_callback) as self.tab_bar:
            with dpg.tab(label="Orientation") as self.main_tab:
                orientation_window = SensorOrientationWindow(self.device)
                orientation_window.submit(dpg.top_container_stack())
                self.staged_view_dict[dpg.top_container_stack()] = orientation_window
            with dpg.tab(label="Terminal"):
                self.terminal_window = SensorTerminalWindow(self.device, self.macro_manager)
                self.terminal_window.submit(dpg.top_container_stack())     
                self.staged_view_dict[dpg.top_container_stack()] = self.terminal_window                          
            with dpg.tab(label="Data Charts"):
                self.data_window = SensorDataChartsWindow(self.device)
                self.data_window.submit(dpg.top_container_stack())   
                self.staged_view_dict[dpg.top_container_stack()] = self.data_window
            with dpg.tab(label="EEPTS"):
                eepts_window = EeptsWindow(self.device)
                eepts_window.submit(dpg.top_container_stack())   
                self.staged_view_dict[dpg.top_container_stack()] = eepts_window               
            with dpg.tab(label="Calibration"):
                self.calibration_window = SensorCalibrationWindow(self.device)
                self.calibration_window.submit(dpg.top_container_stack())
                self.staged_view_dict[dpg.top_container_stack()] = self.calibration_window
            with dpg.tab(label="Settings"):
                self.settings_window = SensorSettingsWindow(self.device)
                self.settings_window.submit(dpg.top_container_stack())
                self.staged_view_dict[dpg.top_container_stack()] = self.settings_window
            dpg.add_tab_button(label="          ")
            dpg.bind_item_theme(dpg.last_item(), SensorMasterWindow.INVISIBLE_THEME)
            dpg.add_tab_button(label="Disconnect", callback=self.__disconnect_selected)
            dpg.bind_item_theme(dpg.last_item(), SensorMasterWindow.DISCONNECT_THEME)
        dpg.pop_container_stack()

        self.open_tab = self.main_tab
        #Have to initialize the tab value for DPG to track it
        #Visuals will work without this, but dpg.get_value() on notify_opened would not
        dpg.set_value(self.tab_bar, self.open_tab)
        self.notify_opened()

    def load_bootloader_windows(self):
        dpg.push_container_stack(self.child_window)
        self.staged_view_dict: dict[int,StagedView] = {}
        with dpg.tab_bar(label="Sensor Tabs", callback=self.__tab_callback) as self.tab_bar:  
            with dpg.tab(label="Settings") as self.main_tab:
                settings_window = BootloaderSettingsWindow(self.device)
                settings_window.submit(dpg.top_container_stack())
                self.staged_view_dict[dpg.top_container_stack()] = settings_window
            with dpg.tab(label="Terminal"):
                terminal_window = BootloaderTerminalWindow(self.device)
                terminal_window.submit(dpg.top_container_stack())     
                self.staged_view_dict[dpg.top_container_stack()] = terminal_window                          
            dpg.add_tab_button(label="          ")
            dpg.bind_item_theme(dpg.last_item(), SensorMasterWindow.INVISIBLE_THEME)
            dpg.add_tab_button(label="Disconnect", callback=self.__disconnect_selected)
            dpg.bind_item_theme(dpg.last_item(), SensorMasterWindow.DISCONNECT_THEME)
        dpg.pop_container_stack()

        self.open_tab = self.main_tab
        #Have to initialize the tab value for DPG to track it
        #Visuals will work without this, but dpg.get_value() on notify_opened would not
        dpg.set_value(self.tab_bar, self.open_tab)
        self.notify_opened()

    def on_sensor_opened(self):
        self.connection_window.delete()
        self.connection_window = None
        dpg.delete_item(self.child_window, children_only=True)
        
        if self.device.in_bootloader:
            self.load_bootloader_windows()
        else:
            self.load_firmware_windows()
        

    def notify_opened(self):
        if self.deleted or self.staged_view_dict is None: return
        self.staged_view_dict[dpg.get_value(self.tab_bar)].notify_opened()

    def notify_closed(self):
        if self.deleted or self.staged_view_dict is None: return
        self.staged_view_dict[dpg.get_value(self.tab_bar)].notify_closed()

    def __tab_callback(self, sender, app_data, user_data):
        if self.deleted: return
        if self.open_tab is not None and self.open_tab != app_data:
            self.staged_view_dict[self.open_tab].notify_closed()
        self.open_tab = app_data
        self.staged_view_dict[app_data].notify_opened()

    def __disconnect_selected(self):
        self.device.disconnect()

    def delete(self):
        if self.staged_view_dict is not None:
            for window in self.staged_view_dict.values():
                window.delete()
        if self.connection_window is not None:
            self.connection_window.delete()
        super().delete()
        self.deleted = True

Z_DIST=50
class SensorConnectionWindow(StagedView):

    def __init__(self, device: ThreespaceDevice, connected_callback: Callable):
        self.texture_width = 400
        self.texture_height = 400

        with dpg.texture_registry() as self.texture_registry:
            self.texture = dpg.add_raw_texture(width=self.texture_width, height=self.texture_height, default_value=[],  format=dpg.mvFormat_Float_rgba)

        #render the object
        self.sensor_obj = GlOrientationViewer(obj_lib.MiniSensorObj, GL_Renderer.text_renderer, GL_Renderer.base_font,
                                                    self.texture_width, self.texture_height,
                                                    background_color=(0, 0, 0, 0), tl_arrows=False, model_arrows=False)
        self.sensor_texture = TextureRenderer(self.texture_width, self.texture_height)
        self.sensor_obj.set_distance(50)
        self.sensor_obj.set_orientation_quat(gl_sensor_to_gl_quat(quaternion.angles_to_quaternion([45, -45], "YX")))
        with self.sensor_texture:
            self.sensor_obj.render()

        #Put the image into the DPG texture
        texture = np.flip(self.sensor_texture.get_texture_pixels(), 0)
        dpg.set_value(self.texture, texture.flatten())

        #Clean up the GL texture resources since only draws once
        self.sensor_obj.delete()
        self.sensor_texture.destroy()

        #Setup the UI
        button_width = 300

        with dpg.stage(label="Connection Stage") as self._stage_id:
            with dpg.child_window(border=False) as self.window:
                with dpg.table(header_row=False):
                    dpg.add_table_column()
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=self.texture_width)
                    dpg.add_table_column()
                    with dpg.table_row():
                        dpg.add_table_cell()
                        dpg.add_image(self.texture)
                dpg.add_child_window(border=False, height=-150) #Weird way of doing spacing
                with dpg.table(header_row=False, borders_innerV=True):
                    dpg.add_table_column()
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=button_width)
                    dpg.add_table_column()
                    with dpg.table_row():
                        dpg.add_table_cell()
                        button = dpg.add_button(label="Connect", callback=self.__on_connect_requested, width=-1)
                        dpg.bind_item_font(button, FontManager.DEFAULT_FONT_LARGE)
                        dpg.bind_item_theme(button, theme_lib.connect_button_theme)

        self.device = device
        self.callback = connected_callback
    
    def __on_connect_requested(self):
        try:
            self.device.open()
        except Exception as e:
            Logger.log_error(f"Failed to connect to {self.device.name}")
            Logger.log_error(f"Failed to connect to {str(e)}")
            self.display_connection_error()
            return

        Logger.log_info(f"Connected to {self.device.name}")
        if self.callback:
            self.callback()

    def display_connection_error(self):
        with dpg.window(modal=True, no_resize=True, no_move=True) as popup:
            dpg.add_text("Failed to connect!")
            with dpg.table(header_row=False):
                dpg.add_table_column()
                dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column()
                with dpg.table_row():
                    dpg.add_table_cell()
                    dpg.add_button(label="Ok", callback=lambda: dpg.delete_item(popup), width=-1)
                    
        dpg.render_dearpygui_frame()
        dpg.render_dearpygui_frame()
        dpg_ext.center_window(popup)

    def delete(self):
        dpg.delete_item(self.texture_registry)
        return super().delete()

class SensorTerminalWindow(StagedView):
    """
    Creates a terminal display visual.
    To display, must call submit and pass
    the parent container or use within a 
    context with block
    """

    MAX_COMMAND_HISTORY = 50

    def __init__(self, threespace_device: ThreespaceDevice, macro_manager: MacroManager):
        self.device = threespace_device
        self.macro_manager = macro_manager

        with dpg.stage(label="Sensor Terminal Stage") as self._stage_id:
            self.terminal = MultilineText(max_messages=2000)
            self.terminal.submit(dpg.top_container_stack())
            
            with dpg.item_handler_registry(label="Terminal Visible Handler") as self.terminal_handler:
                dpg.add_item_visible_handler(callback=self.__on_terminal_visible)

            with dpg.group(horizontal=True):
                dpg.add_text("Command:")
                with dpg.group() as self.command_input_group:
                    #Please modify where this is recreated as well (setCommandInputValue)
                    self.command_input = dpg.add_input_text(width=-50, on_enter=True, callback=self.__on_send_enter_command)
                dpg.add_button(label="Send", callback=self.__on_send_command)
            dpg.add_separator()
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("Macros:")
                with dpg.child_window(resizable_y=False, height=43, width=-33, horizontal_scrollbar=True, border=False):
                    with dpg.group(horizontal=True) as self.macro_container:
                        pass
                dpg.add_image_button(texture_lib.setting_icon_texture.texture, label="Macro CFG Button", width=16, height=16, callback=self.__open_macro_window)
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_text("Device Name:")
                dpg.add_input_text(width=200, default_value=threespace_device.name, callback=self.__on_device_name_changed)
            with dpg.group(horizontal=True):
                self.color = dpg.add_color_edit(display_mode=dpg.mvColorEdit_rgb, no_alpha=True, width=200)
                dpg.add_button(label="Set LED",callback=self.__on_set_led)
            with dpg.group(horizontal=True):
                dpg.add_text("Port:")
                dpg.add_text(str(self.device.com_port))

            #Visible Handler doesn't work on the window, sorta dissapointing, so just use the clear button
            dpg.bind_item_handler_registry(self.terminal.clear_button, self.terminal_handler)
            self.line = ""
            
            self.streaming_paused = False

        #Setup command history functionality
        self.command_history = []
        self.cur_command_index = 0
        with dpg.handler_registry() as self.key_handler:
            dpg.add_key_press_handler(dpg.mvKey_Up, callback=self.__key_handler)
            dpg.add_key_press_handler(dpg.mvKey_Down, callback=self.__key_handler)

        #Setup macros
        self.__load_macros()
        self.macro_manager.on_modified.subscribe(self.__on_macros_modified)
        self.macro_config_window = None

    def notify_opened(self):
        self.streaming_paused = False

    def notify_closed(self):
        try:
            self.device.resume_streaming(self)
            self.streaming_paused = False
        except Exception as e: 
            self.device.report_error(e)

    def __open_macro_window(self):
        self.macro_config_window = MacroConfigurationWindow(self.macro_manager)
        dpg.render_dearpygui_frame() #Must be called before center window so the size information is known
        dpg_ext.center_window(self.macro_config_window.modal)

    def __on_macros_modified(self):
        self.macro_config_window = None
        self.__load_macros()

    def __load_macros(self):
        dpg.delete_item(self.macro_container, children_only=True)
        dpg.push_container_stack(self.macro_container)
        for macro in self.macro_manager.macros:
            dpg.add_button(label=macro.name, callback=self.__execute_macro, user_data=macro)
        dpg.pop_container_stack()

    def __execute_macro(self, sender, app_data, user_data):
        macro: TerminalMacro = user_data
        if len(macro.text) == 0: return
        self.send_command(macro.text)


    def __on_device_name_changed(self, sender, app_data, user_data):
        self.device.name = app_data
    
    def __on_set_led(self, sender, app_data, user_data):
        color = dpg.get_value(self.color)
        color = [int(color[i]) for i in range(3)]

        try:
            self.device.set_led_color(color)
        except Exception as e: 
            self.device.report_error(e)

    def __key_handler(self, sender, app_data, user_data):
        focused = dpg.is_item_focused(self.command_input) and dpg.is_item_active(self.command_input)
        if not focused: return

        if app_data == dpg.mvKey_Up:
            new_command_index = self.cur_command_index + 1
        elif app_data == dpg.mvKey_Down:
            new_command_index = self.cur_command_index - 1
        else:
            return
        
        if new_command_index < 1 or new_command_index > len(self.command_history):
            return
        
        self.cur_command_index = new_command_index
        self.__set_command_input_value(self.command_history[-self.cur_command_index])

    def __set_command_input_value(self, value: str):
        #You can't set the value while the input text is active/focused... so work around is to delete it and recreate it, then set focus
        #This does mean the text will be all selected, and there is no way around this
        #https://github.com/hoffstadt/DearPyGui/issues/1442
        focused = dpg.is_item_focused(self.command_input) and dpg.is_item_active(self.command_input)
        dpg.delete_item(self.command_input)
        self.command_input = dpg.add_input_text(width=-50, on_enter=True, callback=self.__on_send_enter_command,
                           default_value=value, parent=self.command_input_group)
        if focused:
            dpg.focus_item(self.command_input)

    #The reason this is seperated is so focus can be returned
    #to the text box if it was triggered that way
    def __on_send_enter_command(self, sender, app_data):
        self.__on_send_command(sender, app_data)
        dpg.focus_item(self.command_input)

    def __on_send_command(self, sender, app_data):
        with dpg_lock():
            #Get the command
            ascii_command = dpg.get_value(self.command_input)

            #Reset History/Input
            dpg.set_value(self.command_input, "")
            self.cur_command_index = 0

            #Update History
            if len(self.command_history) == 0 or self.command_history[-1] != ascii_command: #Add new commands to the command history
                self.command_history.append(ascii_command)
                if len(self.command_history) > SensorTerminalWindow.MAX_COMMAND_HISTORY:
                    del self.command_history[0]
            
            #Actually attempt to send it
            self.send_command(ascii_command)

    def send_command(self, command: str):
        #Attempt to pause streaming if it hasn't been paused yet
        if not self.streaming_paused:
            try:
                self.streaming_paused = False
                self.streaming_paused = self.device.pause_streaming(self)
                if not self.streaming_paused:
                    self.terminal.add_message(f"{self.device.name} can not send commands via terminal while data streaming is locked.")
                    Logger.log_warning(f"{self.device.name} can not send commands via terminal while data streaming is locked.")
                    return
            except Exception as e:
                self.device.report_error(e)
        
        self.terminal.add_message(command)
        try:
            success = self.device.send_ascii_command(command)
            if not success:
                Logger.log_warning(f"Failed to send command {command} to {self.device.name} via terminal.")
        except Exception as e:
            self.device.report_error(e)

    def __read_terminal(self):
        if self.device.is_api_streaming():
            return
        data = self.device.read_com_port()

        if len(data) > 0:
            self.line += str(data)
        lines = self.line.split('\r\n')
        if len(lines) <= 1: #When a newline is present, will be atleast 2
            return
        self.line = lines[-1] #The last value in the split did not have a newline after it, or is empty as the last char was a newline
        num_full_lines = len(lines) - 1
        if num_full_lines > 0:
            for i in range(num_full_lines):
                self.terminal.add_message(lines[i], immediate_draw=False) #For speed purposes at very fast streaming
            self.terminal.update()

    def __on_terminal_visible(self, sender, app_data):
        """
        A polling method of reading, and manually
        waiting for newline before outputting any data.
        Also accounts for multiple newlines
        """

        #Needs to be done in the main loop to not steal responses from windows, such
        #as orientation, changing settings while shutting down
        MainLoopEventQueue.queue_event(self.__read_terminal)

    def submit(self, parent=None):
        """
        Puts the SensorWindow in the parent component,
        else creates its own window
        """
        if parent is not None:
            self.container = parent
            dpg.push_container_stack(self.container)
        else:
            self.container = dpg.add_window(label="SensorTerminalWindow", pos=(200, 200))
            dpg.push_container_stack(self.container)

        dpg.unstage(self._stage_id)
       
        dpg.pop_container_stack()

    def delete(self):
        dpg.delete_item(self.terminal_handler)
        dpg.delete_item(self.key_handler)
        del self.command_history
        self.terminal.destroy()
        self.macro_manager.on_modified.unsubscribe(self.__on_macros_modified)
        super().delete()

import dpg_ext.dearpygui_grid as dpg_grid

from utility import WatchdogTimer
from dpg_ext.dynamic_button import DynamicButton
class SensorOrientationWindow(StagedView):

    SENSOR_OBJ_GL = None
    SENSOR_BASE_TEXTURE = None

    SENSOR_TEXTURE_RENDERER = None

    TEXTURE_WIDTH = 800
    TEXTURE_HEIGHT = 800

    def __init__(self, device: ThreespaceDevice):
        self.device = device

        self.streaming_hz = 100
        self.streaming_enabled = False
        self.quat = [0, 0, 0, 1]

        self.hide_sensor = False
        
        self.orientation_viewer = GlOrientationViewer(obj_lib.MiniSensorObj, GL_Renderer.text_renderer, GL_Renderer.base_font,
                                                      SensorOrientationWindow.TEXTURE_WIDTH, SensorOrientationWindow.TEXTURE_HEIGHT)

        if SensorOrientationWindow.SENSOR_TEXTURE_RENDERER is None:
            SensorOrientationWindow.SENSOR_TEXTURE_RENDERER = TextureRenderer(SensorOrientationWindow.TEXTURE_WIDTH, SensorOrientationWindow.TEXTURE_HEIGHT)
            self.orientation_viewer.set_orientation_quat([0, 0, 0, 1])
            with SensorOrientationWindow.SENSOR_TEXTURE_RENDERER:
                self.orientation_viewer.render()
            SensorOrientationWindow.SENSOR_BASE_TEXTURE = SensorOrientationWindow.SENSOR_TEXTURE_RENDERER.get_texture_pixels()
            SensorOrientationWindow.SENSOR_BASE_TEXTURE = np.flip(SensorOrientationWindow.SENSOR_BASE_TEXTURE, 0).flatten()

        with dpg.texture_registry() as self.texture_registry:
            self.texture = dpg.add_raw_texture(width=SensorOrientationWindow.TEXTURE_WIDTH, height=SensorOrientationWindow.TEXTURE_HEIGHT, default_value=SensorOrientationWindow.SENSOR_BASE_TEXTURE,  format=dpg.mvFormat_Float_rgba)

        with dpg.stage(label="Orientation Stage") as self._stage_id:
            with dpg.child_window(width=-1, height=-1) as self.child_window:
                self.grid = dpg_grid.Grid(2, 1, dpg.last_container(), rect_getter=dpg_ext.get_global_rect, overlay=False)
                command_window_width = 250
                self.grid.cols[1].configure(size=command_window_width) #Settings bar is a static size
                self.grid.offsets = 8, 8, 8, 8 #Compensating for title bar and scrollbar
                self.image = dpg.add_image(self.texture)
                with dpg.child_window(border=False) as control_window:
                    logo_image = dpg.add_image(texture_lib.logo_texture.texture)
                    with dpg.child_window(label="Components") as components_enabled_window:
                        dpg.add_text("Components")
                        self.accel_enabled = dpg.add_checkbox(label="Accelerometer", 
                                                callback=self.enable_component, user_data=device.set_accel_enabled)                        
                        self.mag_enabled = dpg.add_checkbox(label="Magnetometer", 
                                                callback=self.enable_component, user_data=device.set_mag_enabled)
                        self.gyro_enabled = dpg.add_checkbox(label="Gyroscope", 
                                                callback=self.enable_component, user_data=device.set_gyro_enabled)
                    with dpg.child_window(label="Program") as program_window:
                        dpg.add_text("Program")
                        dpg.add_checkbox(label="Display Sensor", default_value=True, callback=self.__on_hide_sensor)
                        dpg.add_checkbox(label="Display Arrows", default_value=True, enabled=False)
                        with dpg.group(horizontal=True):
                            dpg.add_text("Interval (us):")
                            self.interval_drag = dpg.add_drag_float(default_value=self.streaming_hz, max_value=threespace_consts.STREAMING_MAX_HZ, 
                                               min_value=1, clamped=True, width=-1, format="%.1f")
                    with dpg.child_window(label="Commands") as commands_window:
                        dpg.add_text("Commands")
                        with dpg.table(header_row=False):
                            dpg.add_table_column(init_width_or_weight=60)
                            dpg.add_table_column(init_width_or_weight=30)
                            with dpg.table_row():
                                dpg.add_button(label="Base Tare", width=-1, callback=self.generic_device_command,
                                               user_data=[device.base_tare_with_current_orientation])
                                dpg.add_button(label="Reset", width=-1, callback=self.generic_device_command,
                                               user_data=[device.set_base_tare, [0, 0, 0, 1]])
                            with dpg.table_row():
                                dpg.add_button(label="Tare", width=-1, callback=self.generic_device_command,
                                               user_data=[device.tare_with_current_orientation])
                                dpg.add_button(label="Reset", width=-1, callback=self.generic_device_command,
                                               user_data=[device.set_tare, [0, 0, 0, 1]])
                            with dpg.table_row():
                                dpg.add_button(label="Base Offset", width=-1, callback=self.generic_device_command,
                                               user_data=[device.base_offset_with_current_orientation])
                                dpg.add_button(label="Reset", width=-1, callback=self.generic_device_command,
                                               user_data=[device.set_base_offset, [0, 0, 0, 1]])
                            with dpg.table_row():
                                dpg.add_button(label="Offset", width=-1, callback=self.generic_device_command,
                                               user_data=[device.offset_with_current_orientation])
                                dpg.add_button(label="Reset", width=-1, callback=self.generic_device_command,
                                               user_data=[device.set_offset, [0, 0, 0, 1]])
                        dpg.add_button(label="Auto Calibrate Gyros", width=-1, callback=self.generic_device_command,
                                       user_data=[device.start_gyro_autocalibration])
                        dpg.add_button(label="Commit", width=-1, callback=self.generic_device_command,
                                       user_data=[device.commit_settings])                  
                self.grid.push(self.image, 0, 0)#, max_size = (400, 400))
                self.grid.push(control_window, 1, 0)
                self.grid2 = dpg_grid.Grid(1, 5, control_window, rect_getter=dpg_ext.get_global_rect, overlay=False)
                self.grid2.offsets = 8, 0, 0, 0
                self.grid2.spacing = 3, 3, 3, 3
                self.grid2.push(logo_image, 0, 0)
                self.grid2.rows[0].configure(size=command_window_width * texture_lib.logo_texture.height / texture_lib.logo_texture.width)
                self.grid2.push(components_enabled_window, 0, 1)
                self.grid2.rows[1].configure(size=140)
                self.grid2.push(program_window, 0, 2)
                self.grid2.rows[2].configure(size=140)
                self.grid2.push(commands_window, 0, 4)
                self.grid2.rows[4].configure(size=245)
        
        with dpg.item_handler_registry(label="Orientation Visible Handler") as self.visible_handler:
            dpg.add_item_visible_handler(callback=self.__on_visible)
        dpg.bind_item_handler_registry(self.image, self.visible_handler)

        with dpg.item_handler_registry(label="Orientation Interval Edited Handler") as self.edited_handler:
            dpg.add_item_deactivated_after_edit_handler(callback=self.__on_interval_slider)
        dpg.bind_item_handler_registry(self.interval_drag, self.edited_handler)

        self.reload_dynamic_settings()

    def enable_component(self, sender, app_data, user_data):
        enabled = app_data
        component_func = user_data
        try:
            component_func(enabled)
        except Exception as e:
            self.device.report_error(e)
    
    def generic_device_command(self, sender, app_data, user_data):
        func = user_data[0]
        args = user_data[1:]
        try:
            func(*args)
        except Exception as e:
            self.device.report_error(e)

    def update_image(self):
        rect = dpg.get_item_rect_size(self.image)

        self.orientation_viewer.set_perspective(*rect)
        self.orientation_viewer.set_model_visible(not self.hide_sensor)
        self.orientation_viewer.set_orientation_quat(gl_sensor_to_gl_quat(self.quat))
        with SensorOrientationWindow.SENSOR_TEXTURE_RENDERER:
            self.orientation_viewer.render()
        pixels = SensorOrientationWindow.SENSOR_TEXTURE_RENDERER.get_texture_pixels()
        pixels = np.flip(pixels, 0)
        dpg.set_value(self.texture, pixels.flatten())

    def __on_hide_sensor(self, sender, app_data, user_data):
        self.hide_sensor = not app_data

    def __reregister_callback(self):
        if not self.streaming_enabled: return
        try:
            self.device.unregister_streaming_callback(self.__on_orientation_updated)
            self.device.register_streaming_callback(self.__on_orientation_updated, hz=self.streaming_hz, only_newest=True)
        except Exception as e:
            self.device.report_error(e)

    def update_streaming_speed(self, hz: float):
        if hz < 0 or hz > threespace_consts.STREAMING_MAX_HZ: return
        self.streaming_hz = hz
        #This needs to happen synchronously in the main loop to avoid concurrency issues with the streaming manager
        #TODO: Change the streaming manager to have a lock around its function calls
        MainLoopEventQueue.queue_event(self.__reregister_callback)

    def __on_interval_slider(self, sender, app_data, user_data):
        self.update_streaming_speed(dpg.get_value(self.interval_drag))

    def __on_orientation_updated(self, status: ThreespaceStreamingStatus):
        if status == ThreespaceStreamingStatus.Data:
            self.quat = self.device.get_streaming_value(StreamableCommands.GetTaredOrientation)
            self.update_image()
        elif status == ThreespaceStreamingStatus.Reset:
            self.__stop_viewer()

    def __start_viewer(self):
        if self.streaming_enabled:
            return
        
        try:
            self.streaming_enabled = self.device.register_streaming_command(self, StreamableCommands.GetTaredOrientation)
            if self.streaming_enabled:
                #hertz = min(dpg.get_frame_rate(), 100)
                hertz = self.streaming_hz
                self.device.register_streaming_callback(self.__on_orientation_updated, hz=hertz, only_newest=True)
        except Exception as e:
            self.device.report_error(e)

    def __stop_viewer(self):
        if self.streaming_enabled:
            try:
                self.device.unregister_streaming_command(self, StreamableCommands.GetTaredOrientation)
                self.device.unregister_streaming_callback(self.__on_orientation_updated)
            except Exception as e:
                self.device.report_error(e)
            self.streaming_enabled = False

    def reload_dynamic_settings(self):
        #These may be dirty since last load
        try:
            dpg.set_value(self.accel_enabled, self.device.is_accel_enabled())
            dpg.set_value(self.mag_enabled, self.device.is_mag_enabled())
            dpg.set_value(self.gyro_enabled, self.device.is_gyro_enabled())
        except Exception as e:
            self.device.report_error(e)

    def notify_opened(self):
        self.__start_viewer()
        self.reload_dynamic_settings()

    def notify_closed(self):
        self.__stop_viewer()

    def __on_visible(self, sender, app_data):
        self.grid()
        self.grid2()

    def delete(self):
        dpg.delete_item(self.edited_handler)
        dpg.delete_item(self.visible_handler)
        dpg.delete_item(self.texture_registry)
        self.grid.clear()
        self.grid2.clear()
        self.orientation_viewer.delete()
        return super().delete()


from data_charts import DataChartAxisOption
import data_charts
class SensorDataWindow:

    MAX_POINTS_PER_AXIS = 500
    THEMES = None

    def __init__(self, options: dict[str,DataChartAxisOption], device: ThreespaceDevice,  default_value=None):
        if SensorDataWindow.THEMES is None:
            SensorDataWindow.THEMES = [theme_lib.plot_x_line_theme, theme_lib.plot_y_line_theme, theme_lib.plot_z_line_theme, theme_lib.plot_w_line_theme]
        self.device = device

        self.options = options
        self.keys = list(options.keys())

        self.cur_axis = default_value or self.keys[0]
        self.cur_option = self.options[self.cur_axis]
        self.cur_command_param = None

        self.streaming_hz = 100
        self.streaming = False
        self.opened = False

        self.paused = False
        self.vertical_line_pos = None

        #Used for speed optimization with the parent window
        self.__delay_registration = False

        self.pad_percent = 0.05

        self.text = []
        self.series = []
        self.y_data: list[list] = [] #One set per series
        self.x_data: list[int] = [] #Shared x axis across all series
        with dpg.child_window() as self.window:
            self.dropdown = FilteredDropdown(items=self.keys, default_item=self.cur_axis, 
                                        width=-1, allow_custom_options=False, allow_empty=False, 
                                        callback=self.__on_stream_command_changed)
            self.dropdown.submit()
            with dpg.group(horizontal=True):
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_x, show=False))
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_y, show=False))
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_z, show=False))
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_w, show=False))
                self.param_dropdown = dpg.add_combo(items=[], default_value="", show=False, callback=self.__on_stream_param_changed, width=-1)
            with dpg.plot(width=-1, height=-1) as self.plot:
                self.x_axis = dpg.add_plot_axis(dpg.mvXAxis, )
                with dpg.plot_axis(dpg.mvYAxis) as self.y_axis:
                    self.vertical_line = dpg.add_inf_line_series(x=[])
                    dpg.bind_item_theme(self.vertical_line, theme_lib.plot_indicator_theme)
        
        self.build_stream_window()
        self.build_param_window()

    def set_vline_pos(self, x: float):
        if x is None: #Remove the line
            if self.vertical_line_pos is not None:
                self.vertical_line_pos = None
                dpg.configure_item(self.vertical_line, x=[])
                self.set_current_text_values()
        else:
            if x < dpg.get_axis_limits(self.x_axis)[0]: #Only add the line if in range of the current data
                self.set_vline_pos(None)
                return
            self.vertical_line_pos = x
            dpg.configure_item(self.vertical_line, x=[x])
            self.set_text_values_by_x(x)

    def set_text_values_by_x(self, x):
        if len(self.series) == 0: return
        min_index = None
        max_index = None
        x_data = dpg.get_value(self.series[0])[0] #Gotta used the cache X data because if paused, the x data still updates but want to do based on what is graphed
        for i in range(len(x_data)-1):
            if x_data[i] <= x <= x_data[i+1]:
                min_index = i
                max_index = i + 1
                break
        
        if min_index is None:
            return
        
        min_x = x_data[min_index]
        max_x = x_data[max_index]
        percent = (x - min_x) / (max_x - min_x)


        num_axes = min(len(self.text), len(self.y_data))
        for i in range(num_axes):
            y_data = dpg.get_value(self.series[i])[1]
            min_y = y_data[min_index]
            max_y = y_data[max_index]
            y = min_y + percent * (max_y - min_y)
            dpg.set_value(self.text[i], f"{y: .05f}")

    def set_current_text_values(self):
        if len(self.series) == 0: return
        x_data = dpg.get_value(self.series[0])[0]
        if len(x_data) == 0: return
        self.set_text_values_by_x(x_data[-1])

    def __on_stream_command_changed(self, sender, app_data):
        if app_data == self.cur_axis: return #It didn't change
        self.stop_data_chart()
        self.cur_axis = app_data
        self.cur_option = self.options[self.cur_axis]
        self.cur_command_param = None
        if self.cur_option is not None and self.cur_option.valid_params is not None and len(self.cur_option.valid_params) > 0:
            self.cur_command_param = self.cur_option.valid_params[0]
        self.build_param_window()
        self.build_stream_window()
        self.start_data_chart()
    
    def __on_stream_param_changed(self, sender, app_data):
        self.cur_command_param = int(app_data)
        self.stop_data_chart()
        self.start_data_chart()

    def set_pause_state(self, paused: bool):
        self.paused = paused

    def build_param_window(self):
        if self.cur_option is None or self.cur_option.valid_params is None:
            dpg.hide_item(self.param_dropdown)
            return
        else:
            valid_params = self.cur_option.valid_params
            dpg.configure_item(self.param_dropdown, items=valid_params, show=True)
            dpg.set_value(self.param_dropdown, self.cur_command_param)

    def streaming_callback(self, status: ThreespaceStreamingStatus):
        if status == ThreespaceStreamingStatus.Data:
            timestamp = self.device.get_streaming_value(StreamableCommands.GetTimestamp)
            self.x_data.append(timestamp / 1000000) #Convert from microseconds to seconds
            if len(self.x_data) > SensorDataWindow.MAX_POINTS_PER_AXIS:
                self.x_data.pop(0)
            data = self.device.get_streaming_value(self.cur_option.cmd_enum, self.cur_command_param)
            if not isinstance(data, list):
                data = [data]
            for i, v in enumerate(data):
                self.y_data[i].append(v)
                if len(self.y_data[i]) > SensorDataWindow.MAX_POINTS_PER_AXIS:
                    self.y_data[i].pop(0)
        elif status == ThreespaceStreamingStatus.DataEnd: #Only update the graph after this update of the streaming is done
            if self.paused: return #Pause only pauses the display, not the collection
            for i, series in enumerate(self.series):
                dpg.configure_item(series, x=self.x_data, y=self.y_data[i])
                if i < len(self.text): #Set text to the last number
                    dpg.set_value(self.text[i], f"{self.y_data[i][-1]: .05f}")
                
            #Calculate new y bounds
            max_y = max(max(data) for data in self.y_data)
            min_y = min(min(data) for data in self.y_data)
            y_range = max_y - min_y
            if not any(v is None for v in self.cur_option.bounds_y):
                y_range = max(y_range, self.cur_option.bounds_y[1] - self.cur_option.bounds_y[0])
            padding = y_range * self.pad_percent
            min_y -= padding
            max_y += padding
            if self.cur_option.bounds_y[1] is not None:
                max_y = max(self.cur_option.bounds_y[1], max_y)
            if self.cur_option.bounds_y[0] is not None:
                min_y = min(self.cur_option.bounds_y[0], min_y)

            dpg.fit_axis_data(self.x_axis)
            dpg.set_axis_limits(self.y_axis, min_y, max_y)     
            if len(self.x_data) == SensorDataWindow.MAX_POINTS_PER_AXIS:
                #Only take over the labels once it fills the graph. This prevents DPG sometimes auto flashing between whole second and half second intervals
                min_x = self.x_data[0]
                if self.vertical_line_pos is not None and min_x > self.vertical_line_pos:
                    self.set_vline_pos(None)
                min_x = int(self.x_data[0])
                max_x = int(self.x_data[-1])
                axis_ticks = list(range(min_x, max_x + 1))
                axis_ticks = tuple([(str(v), v) for v in axis_ticks])
                dpg.set_axis_ticks(self.x_axis, axis_ticks)   
            else:
                dpg.reset_axis_ticks(self.x_axis)
        elif status == ThreespaceStreamingStatus.Reset:
            self.stop_data_chart()

    def build_stream_window(self):
        """Using current state, rebuild the plot window to be for the current state"""
        num_out = 0 if self.cur_option is None else self.cur_option.cmd.num_out_params

        #Show up to 4 text objects for the graph
        for i, text in enumerate(self.text):
            if i < num_out:
                dpg.show_item(text)
                dpg.set_value(text, f"{0: .05f}")
            else:
                dpg.hide_item(text)
        
        #Add the line series
        dpg.delete_item(self.y_axis, children_only=True)
        self.series.clear()
        self.x_data.clear()
        self.y_data.clear()
        dpg.push_container_stack(self.y_axis)
        self.vertical_line = dpg.add_inf_line_series(x=[])
        dpg.bind_item_theme(self.vertical_line, theme_lib.plot_indicator_theme)
        for i in range(num_out):
            self.y_data.append([])
            self.series.append(dpg.add_line_series(self.x_data, self.y_data[i], label=f"{i}"))
            if i < len(SensorDataWindow.THEMES):
                dpg.bind_item_theme(self.series[-1], SensorDataWindow.THEMES[i])
        dpg.pop_container_stack()

    def clear_chart(self):
        self.x_data.clear()
        for i, series in enumerate(self.series):
            self.y_data[i].clear()
            dpg.configure_item(series, x=self.x_data, y=self.y_data[i])

    def start_data_chart(self):
        if self.streaming or self.cur_option is None: return #Already streaming or nothing to stream
        if not self.visible: return #The window isn't available for streaming
        try:
            self.streaming = self.device.register_streaming_command(self, self.cur_option.cmd_enum, self.cur_command_param, immediate_update=not self.__delay_registration)
            if not self.streaming: return
            self.streaming = self.device.register_streaming_command(self, StreamableCommands.GetTimestamp, immediate_update=not self.__delay_registration) #Used for the X axis
            if not self.streaming:
                #Immediate update is false here because no update will have occurred if the previous command failed, so no need to update streaming
                #slots here either. Eventually streaming manager should be changed to handle this type of situation itself.
                self.device.unregister_streaming_command(self, self.cur_option.cmd_enum, self.cur_command_param, immediate_update=not self.__delay_registration)
                return
            self.clear_chart()
            self.device.register_streaming_callback(self.streaming_callback, hz=self.streaming_hz)
        except Exception as e:
            self.streaming = False
            self.device.report_error(e)
        
    def stop_data_chart(self):
        if not self.streaming: return
        try:
            self.device.unregister_streaming_command(self, self.cur_option.cmd_enum, self.cur_command_param, immediate_update=not self.__delay_registration)
            self.device.unregister_streaming_command(self, StreamableCommands.GetTimestamp, immediate_update=not self.__delay_registration)
            self.device.unregister_streaming_callback(self.streaming_callback)
        except Exception as e:
            self.device.report_error(e)
        self.streaming = False

    def delay_streaming_registration(self, delay):
        self.__delay_registration = delay

    def notify_open(self):
        self.opened = True
        self.start_data_chart()

    def notify_closed(self):
        self.stop_data_chart()
        
    def hide(self):
        dpg.hide_item(self.window)
        self.stop_data_chart()

    def show(self):
        dpg.show_item(self.window)
        self.start_data_chart()

    @property
    def visible(self):
        return self.opened and dpg.is_item_shown(self.window)

    def destroy(self):
        self.stop_data_chart()
        self.dropdown.delete()
        dpg.delete_item(self.window)

class SensorDataChartsWindow(StagedView):

    def __init__(self, device: ThreespaceDevice):
        self.device = device
        self.max_rows = 3
        self.max_cols = 3
        self.rows = 2
        self.cols = 2
        self.data_windows: list[list[SensorDataWindow]] = []

        self.options = data_charts.get_all_data_chart_axis_options(device)
        data_charts.modify_options(self.options) #Adds in bounds and stuff

        #Change key to the display name
        self.options = {o.display_name : o for o in self.options.values()}
        #Add in the None option
        new_options = {"None": None}
        new_options.update(self.options)
        self.options = new_options

        self.paused = False

        default_charts = [
            ["Tared Orientation",           "Primary Corrected Gyro Rate", "None"],
            ["Primary Corrected Accel Vec", "Primary Corrected Mag Vec",   "None"],
            ["None",                        "None",                        "None"]
        ]

        with dpg.stage(label="Chart Stage") as self._stage_id:
            with dpg.child_window(width=-1, height=-1, menubar=True) as self.window:
                with dpg.menu_bar() as self.menu_bar:
                    with dpg.menu(label="Configure") as configure_menu:
                        self.num_rows_slider = dpg.add_slider_int(label="#Rows", default_value=self.rows, 
                                                                    max_value=self.max_rows, min_value=1, clamped=True, width=50,
                                                                    callback=self.__on_layout_changed)
                        self.num_cols_slider = dpg.add_slider_int(label="#Cols", default_value=self.cols, 
                                                                    max_value=self.max_cols, min_value=1, clamped=True, width=50,
                                                                    callback=self.__on_layout_changed)
                    self.pause_button = DynamicButton()
                    pause_button = dpg.add_button(label="Pause", callback=self.__on_pause_button)
                    resume_button = dpg.add_button(label="Resume", callback=self.__on_resume_button)
                    self.pause_button.add_button("pause", pause_button, active=True, default=True)
                    self.pause_button.add_button("resume", resume_button)
                    dpg.add_menu_item(label="Popout")
                self.grid = dpg_grid.Grid(self.cols, self.rows, target=dpg.top_container_stack(), overlay=False, rect_getter=dpg_ext.get_global_rect)
                self.grid.offsets = [0, 20, 0, 8] #Make space for the menu bar
                for col in range(self.max_cols): #Build all the windows
                    self.data_windows.append([])
                    for row in range(self.max_rows):
                        window = SensorDataWindow(self.options, device, default_value=default_charts[row][col])
                        self.data_windows[col].append(window)
                        if row < self.rows and col < self.cols:
                            self.grid.push(window.window, col, row)
                        else:
                            window.hide()
            self.grid.configure(cols=self.cols, rows=self.rows)
        
        with dpg.item_handler_registry(label="Data Charts Visible Handler") as self.visible_handler:
            dpg.add_item_visible_handler(callback=self.__on_visible)
        #Child window doesn't have a visible handler but buttons do
        #Don't use the plots of the DataWindows because those need their own handler
        dpg.bind_item_handler_registry(pause_button, self.visible_handler) #This is awkward but it works
        dpg.bind_item_handler_registry(resume_button, self.visible_handler)

    def __on_pause_button(self, sender, app_data, user_data):
        self.pause_button.set_button("resume")
        for col in self.data_windows:
            for window in col:
                window.set_pause_state(True)
        self.paused = True

    def __on_resume_button(self, sender, app_data, user_data):
        self.pause_button.set_button("pause")
        for col in self.data_windows:
            for window in col:
                window.set_pause_state(False)   
        self.paused = False     

    def __on_visible(self, sender, app_data, user_data):
        self.grid()
        if self.paused:
            hovered = any(dpg.is_item_hovered(window.plot) for col in self.data_windows for window in col)
            x = None if not hovered else dpg.get_plot_mouse_pos()[0]
            for col in self.data_windows:
                for window in col:
                    window.set_vline_pos(x)

    #Note: Because of mass opening and closing, the registration is delayed and force updated at the end of this function
    #so only one call has to happen to the actual sensor. This improves speed for opening this window
    def notify_opened(self):
        self.grid()
        for row in self.data_windows:
            for window in row:
                window.delay_streaming_registration(True)
                window.notify_open()
                window.delay_streaming_registration(False)
        try:
            self.device.update_streaming_settings()
        except Exception as e:
            self.device.report_error(e)
    
    def notify_closed(self):
        for row in self.data_windows:
            for window in row:
                window.delay_streaming_registration(True)
                window.notify_closed()
                window.delay_streaming_registration(False)
        try:
            self.device.update_streaming_settings()
        except Exception as e:
            self.device.report_error(e)

    def __on_layout_changed(self, sender, app_data, user_data):
        new_rows = dpg.get_value(self.num_rows_slider)
        new_cols = dpg.get_value(self.num_cols_slider)

        #Remove any removed columns first
        if new_cols < self.cols:
            for col in range(self.cols-1, new_cols-1, -1):
                for row in range(self.rows):
                    window: SensorDataWindow = self.data_windows[col][row]
                    window.delay_streaming_registration(True)
                    window.hide()
                    window.delay_streaming_registration(False)
                    self.grid.pop(window.window)
            self.cols = new_cols
        if new_rows < self.rows:
            for row in range(self.rows-1, new_rows-1, -1):
                for col in range(self.cols):
                    window: SensorDataWindow = self.data_windows[col][row]
                    window.delay_streaming_registration(True)
                    window.hide()
                    window.delay_streaming_registration(False)
                    self.grid.pop(window.window)
            self.rows = new_rows
        
        #Then add back in any new cols or rows
        if new_cols > self.cols:
            for col in range(self.cols, new_cols):
                for row in range(self.rows):
                    window: SensorDataWindow = self.data_windows[col][row]
                    window.delay_streaming_registration(True)
                    window.show()
                    window.delay_streaming_registration(False)
                    self.grid.push(window.window, col, row)
            self.cols = new_cols

        if new_rows > self.rows:
            for row in range(self.rows, new_rows):
                for col in range(self.cols):
                    window: SensorDataWindow = self.data_windows[col][row]
                    window.delay_streaming_registration(True)
                    window.show()
                    window.delay_streaming_registration(False)
                    self.grid.push(window.window, col, row)
            self.rows = new_rows
        
        self.grid.configure(cols=self.cols, rows=self.rows)

        try:
            self.device.update_streaming_settings()
        except Exception as e:
            self.device.report_error(e)

    def delete(self):
        for row in self.data_windows:
            for window in row:
                window.destroy()
        dpg.delete_item(self.visible_handler)
        self.pause_button.delete()
        self.grid.clear()
        return super().delete()


class TableMatrix:

    def __init__(self, rows: int, cols: int):
        self.matrix = [[0.0] * cols for _ in range(rows)]
        self.text_matrix = [[None] * cols for _ in range(rows)]
        with dpg.table(header_row=False, borders_innerH=True, borders_innerV=True, borders_outerH=True, borders_outerV=True):
            for col in range(cols):
                dpg.add_table_column(init_width_or_weight=1/cols, width_stretch=True)
            for row in range(rows):
                with dpg.table_row():
                    for col in range(cols):
                        self.text_matrix[row][col] = dpg.add_text(f"{self.matrix[row][col]:.6f}")
        
    def set_matrix_value(self, row: int, col: int, value: float):
        self.matrix[row][col] = value
        dpg.set_value(self.text_matrix[row][col], f"{value:.6f}")

    def set_matrix(self, matrix: list[list[float]]):
        for row in range(len(matrix)):
            for col in range(len(matrix[row])):
                self.set_matrix_value(row, col, matrix[row][col])
    
    def set_color(self, row: int, col: int, color: list[int]):
        dpg.configure_item(self.text_matrix[row][col], color=color)        

import threading
import time
class SensorSettingsWindow(StagedView):

    def __init__(self, device: ThreespaceDevice):
        with dpg.stage(label="Sensor Settings Stage") as self._stage_id:
            with dpg.file_dialog(width=700, height=400, file_count=1, directory_selector=False, 
                                 callback=self.__on_firmware_file_selected, show=False, modal=True,
                                 default_path=APPLICATION_FOLDER.as_posix()) as self.firmware_selector:
                dpg.add_file_extension(".xml", custom_text="[Firmware]", color=(0, 255, 0))

            try:
                serial_number = device.get_serial_number()
                hardware_version = device.get_hardware_version()
            except Exception as e:
                device.report_error(e)
                return

            with dpg.child_window():
                with dpg.group(horizontal=True):
                    dpg.add_text(f"Serial#:")
                    self.serial_number_text = dpg.add_text(f"0x{serial_number:016X}") 
                with dpg.group(horizontal=True):
                    dpg.add_text(f"Hardware Version:")
                    dpg.add_text(hardware_version)
                with dpg.group(horizontal=True):
                    dpg.add_text("Firmware Version:")
                    self.version_firmware_text = dpg.add_text()     
                    dpg.add_spacer(width=50)
                    dpg.add_button(label="Upload Firmware", callback=lambda: dpg.show_item(self.firmware_selector))          
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Restore Factory Settings", 
                                   callback=lambda: dpg_ext.create_confirm_popup("Are you sure you want to restore factory settings?", 
                                                                         on_confirm=self.restore_factory_settings))
                    dpg.add_button(label="Restart",
                                   callback=lambda: dpg_ext.create_confirm_popup("Are you sure you want to restart the device?", 
                                                                         on_confirm=self.restart_sensor))
                dpg.add_spacer(height=12)
                dpg.add_separator()
                dpg.add_spacer(height=12)
                with dpg.table(width=-1, header_row=False):
                    dpg.add_table_column(init_width_or_weight=200, width_fixed=True)
                    dpg.add_table_column()
                    with dpg.table_row():
                        dpg.add_text("Available Gyros:")
                        self.gyro_detected_text = dpg.add_text()
                    with dpg.table_row():
                        dpg.add_text("Available Accels:")
                        self.accel_detected_text = dpg.add_text()
                    with dpg.table_row():
                        dpg.add_text("Available Mags:")
                        self.mag_detected_text = dpg.add_text()
                    with dpg.table_row():
                        dpg.add_table_cell()
                        dpg.add_table_cell()
                    with dpg.table_row():
                        dpg.add_text("Filter Mode:")
                        self.filter_mode_text = dpg.add_text()
                dpg.add_spacer(height=12)
                dpg.add_separator()
                dpg.add_spacer(height=12)
                     
        self.device = device
        self.reload_settings()

    def restart_sensor(self):
        try:
            self.device.restart_sensor()
        except Exception as e:
            self.device.report_error(e)

    def restore_factory_settings(self):
        try:
            self.device.restore_factory_settings()
        except Exception as e:
            self.device.report_error(e)

    def reload_settings(self):
        try:
            dpg.set_value(self.version_firmware_text, self.device.get_firmware_version())
            dpg.set_value(self.gyro_detected_text, ' '.join(self.device.get_available_gyros_str()))
            dpg.set_value(self.accel_detected_text, ' '.join(self.device.get_available_accels_str()))
            dpg.set_value(self.mag_detected_text, ' '.join(self.device.get_available_mags_str()))
            dpg.set_value(self.filter_mode_text, self.device.get_filter_mode())
        except Exception as e:
            self.device.report_error(e)
        
    def __run_firmware_update(self, firmware_path: str):
        print("Uploading firmware:", firmware_path)
        firmware_name = pathlib.Path(firmware_path).name
        width = 400
        with dpg.window(label="Firmware Upload", modal=True, no_open_over_existing_popup=False, width=width, 
                        no_close=True, no_move=True, no_resize=True) as popup_window:
            dpg.add_text(f"Uploading firmware {firmware_name}", wrap=width)
            progress_bar = dpg.add_progress_bar(default_value=0, width=-1)
            progress_text = dpg.add_text(f"{0: 3}% complete")
                
        dpg.render_dearpygui_frame() #Not sure why need to render 2 frames before the get rect works correctly, but it does need done
        dpg.render_dearpygui_frame()
        dpg_ext.center_window(popup_window)
        dpg.render_dearpygui_frame()

        firmware_uploader = self.device.get_firmware_uploader()
        firmware_uploader.set_firmware_path(firmware_path)
        def set_percent_complete(percent):
            dpg.set_value(progress_text, f"{int(percent): 3}% complete")
            percent /= 100
            dpg.set_value(progress_bar, percent)
            dpg.render_dearpygui_frame()

        firmware_uploader.set_percent_callback(set_percent_complete)
        success = True
        try:
            firmware_uploader.upload_firmware()
        except Exception as e:
            success = False
            self.device.report_error(e)

        dpg.delete_item(popup_window)
        if success:
            self.reload_settings()

    def __on_firmware_file_selected(self, sender, app_data, user_data):
        selections: dict[str,str] = app_data["selections"]
        if len(selections) == 0: return
        file_name = list(selections.keys())[0]
        file_path = list(selections.values())[0]

        MainLoopEventQueue.queue_event(lambda: self.__run_firmware_update(file_path))

    def delete(self):
        dpg.delete_item(self.firmware_selector)
        super().delete()

class SensorCalibrationWindow(StagedView):

    MATH_IMAGE = None
    TEXTURE_REGISTRY = None

    def __init__(self, device: ThreespaceDevice):
        if SensorCalibrationWindow.MATH_IMAGE is None:
            width, height, channels, data = dpg.load_image((IMAGE_FOLDER / "calibration_math2.png").as_posix())
            with dpg.texture_registry(label="SensorCalibWindowTextureReg") as SensorCalibrationWindow.TEXTURE_REGISTRY:
                SensorCalibrationWindow.MATH_IMAGE = dpg.add_static_texture(width=width, height=height, default_value=data)
        self.device = device

        try:
            self.gyros = device.get_available_gyros()
            self.mags = device.get_available_mags()
            self.accels = device.get_available_accels()
        except Exception as e:
            device.report_error(e)

        default_gyro = None if len(self.gyros) == 0 else self.gyros[0]
        default_mag = None if len(self.mags) == 0 else self.mags[0]
        default_accel = None if len(self.accels) == 0 else self.accels[0]

        self.gradient_descent_wizard = None

        with dpg.stage(label="Sensor Calib Stage") as self._stage_id:
            with dpg.child_window() as self.window:
                with dpg.table(header_row=False):
                    dpg.add_table_column(label="Gyro")
                    dpg.add_table_column(label="Accel")
                    dpg.add_table_column(label="Mag")
                    with dpg.table_row():
                        with dpg.group(horizontal=True):
                            dpg.add_text("Gyro")
                            self.gyro_selection = dpg.add_combo(self.gyros, default_value=default_gyro, fit_width=True, 
                                                                show=len(self.gyros)>1, callback=self.update_gyro_calib)
                        with dpg.group(horizontal=True):
                            dpg.add_text("Accel")
                            self.accel_selection = dpg.add_combo(self.accels, default_value=default_accel, fit_width=True, 
                                                                 show=len(self.accels)>1, callback=self.update_accel_calib)
                        with dpg.group(horizontal=True):
                            dpg.add_text("Mag")
                            self.mag_selection = dpg.add_combo(self.mags, default_value=default_mag, fit_width=True, 
                                                               show=len(self.mags)>1, callback=self.update_mag_calib)
                            dpg.add_child_window(width=-150, height=1, border=False) #Dumb spacing
                            dpg.add_text("Hover for Math", color=theme_lib.color_tooltip)
                            with dpg.tooltip(parent=dpg.last_item()):
                                dpg.add_image(SensorCalibrationWindow.MATH_IMAGE)
                    with dpg.table_row():
                        self.gyro_matrix = TableMatrix(3, 3)
                        self.accel_matrix = TableMatrix(3, 3)
                        self.mag_matrix = TableMatrix(3, 3)
                    with dpg.table_row():
                        self.gyro_bias = TableMatrix(1, 3)
                        self.accel_bias = TableMatrix(1, 3)
                        self.mag_bias = TableMatrix(1, 3)
                    with dpg.table_row():
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="Clear Matrix", callback=lambda: self.clear_gyro_matrix(start=True), 
                                           enabled=len(self.gyros) > 0,)
                            dpg.add_button(label="Clear Bias", callback=lambda: self.clear_gyro_bias(start=True),
                                           enabled=len(self.gyros) > 0)
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="Clear Matrix", callback=lambda: self.clear_accel_matrix(start=True), 
                                           enabled=len(self.accels) > 0)
                            dpg.add_button(label="Clear Bias", callback=lambda: self.clear_accel_bias(start=True), 
                                           enabled=len(self.accels) > 0)
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="Clear Matrix", callback=lambda: self.clear_mag_matrix(start=True),
                                           enabled=len(self.mags) > 0)
                            dpg.add_button(label="Clear Bias", callback=lambda: self.clear_mag_bias(start=True),
                                           enabled=len(self.mags) > 0)
                dpg.add_spacer(height=12)
                dpg.add_separator()      
                dpg.add_spacer(height=12)                                               
                dpg.add_button(label="Gradient Descent Calibration", callback=self.start_gradient_descent_wizard)
                # dpg.add_button(label="Start Gyro Calibration")
                # dpg.add_button(label="Start Mag Ref Calibration")
                # dpg.add_button(label="Start Mag Bias Calibration")

    def start_gradient_descent_wizard(self):
        if self.gradient_descent_wizard is not None: return #This shouldn't be possible, but putting this here anyways
        self.gradient_descent_wizard = GradientDescentCalibrationWizard(self.device, self.__on_gradient_descent_completed)

    def __on_gradient_descent_completed(self, completed_successfully: bool):
        print("Gradient Descent Done:", completed_successfully)
        if not completed_successfully: 
            self.gradient_descent_wizard = None
            return
        result = self.gradient_descent_wizard.get_result()
        self.gradient_descent_wizard = None

        try:
            for accel, calib in result.accels.items():
                self.device.set_accel_calibration(accel, mat=calib.mat, bias=calib.bias)
            for mag, calib in result.mags.items():
                self.device.set_mag_calibration(mag, mat=calib.mat, bias=calib.bias)
        except Exception as e:
            self.device.report_error(e)
        else:
            self.update_accel_calib()
            self.update_mag_calib()

    def update_accel_calib(self):
        if len(self.accels) == 0: return
        accel = dpg.get_value(self.accel_selection)
        try:
            mat, bias = self.device.get_accel_calibration(accel)
        except Exception as e:
            self.device.report_error(e)
            return
        mat = self.calib_to_matrix(mat)
        self.accel_matrix.set_matrix(mat)
        self.accel_bias.set_matrix([bias])

    def update_gyro_calib(self):
        if len(self.gyros) == 0: return
        gyro = dpg.get_value(self.gyro_selection)
        try:
            mat, bias = self.device.get_gyro_calibration(gyro)
        except Exception as e:
            self.device.report_error(e)
            return
        mat = self.calib_to_matrix(mat)
        self.gyro_matrix.set_matrix(mat)
        self.gyro_bias.set_matrix([bias])

    def update_mag_calib(self):
        if len(self.mags) == 0: return
        mag = dpg.get_value(self.mag_selection)
        try:
            mat, bias = self.device.get_mag_calibration(mag)
        except Exception as e:
            self.device.report_error(e)
            return
        mat = self.calib_to_matrix(mat)
        self.mag_matrix.set_matrix(mat)
        self.mag_bias.set_matrix([bias])

    def clear_gyro_matrix(self, start=False):
        if len(self.gyros) == 0: return
        id = dpg.get_value(self.gyro_selection)
        if start:
            dpg_ext.create_confirm_popup(f"Are you sure you want to clear the current gyro{id} matrix?",
                                         on_confirm=self.clear_gyro_matrix)            
            return
        try:
            self.device.set_gyro_calibration(id, mat=self.device.DEFAULT_MATRIX)
        except Exception as e:
            self.device.report_error(e)
            return
        self.update_gyro_calib()

    def clear_gyro_bias(self, start=False):
        if len(self.gyros) == 0: return
        id = dpg.get_value(self.gyro_selection)
        if start:
            dpg_ext.create_confirm_popup(f"Are you sure you want to clear the current gyro{id} bias?",
                                         on_confirm=self.clear_gyro_bias)
            return
        try:
            self.device.set_gyro_calibration(id, bias=self.device.DEFAULT_BIAS)
        except Exception as e:
            self.device.report_error(e)
            return
        self.update_gyro_calib()

    def clear_accel_matrix(self, start=False):
        if len(self.accels) == 0: return
        id = dpg.get_value(self.accel_selection)
        if start:
            dpg_ext.create_confirm_popup(f"Are you sure you want to clear the current accel{id} matrix?",
                                         on_confirm=self.clear_accel_matrix)            
            return
        try:
            self.device.set_accel_calibration(id, mat=self.device.DEFAULT_MATRIX)
        except Exception as e:
            self.device.report_error(e)
            return
        self.update_accel_calib()

    def clear_accel_bias(self, start=False):
        if len(self.accels) == 0: return
        id = dpg.get_value(self.accel_selection)
        if start:
            dpg_ext.create_confirm_popup(f"Are you sure you want to clear the current accel{id} bias?",
                                         on_confirm=self.clear_accel_bias)            
            return
        try:
            self.device.set_accel_calibration(id, bias=self.device.DEFAULT_BIAS)
        except Exception as e:
            self.device.report_error(e)
            return
        self.update_accel_calib()

    def clear_mag_matrix(self, start=False):
        if len(self.mags) == 0: return
        id = dpg.get_value(self.mag_selection)
        if start:
            dpg_ext.create_confirm_popup(f"Are you sure you want to clear the current mag{id} matrix?",
                                         on_confirm=self.clear_mag_matrix)            
            return
        try:
            self.device.set_mag_calibration(id, mat=self.device.DEFAULT_MATRIX)
        except Exception as e:
            self.device.report_error(e)
            return
        self.update_mag_calib()

    def clear_mag_bias(self, start=False):
        if len(self.mags) == 0: return
        id = dpg.get_value(self.mag_selection)
        if start:
            dpg_ext.create_confirm_popup(f"Are you sure you want to clear the current mag{id} bias?",
                                         on_confirm=self.clear_mag_bias)            
            return
        try:
            self.device.set_mag_calibration(id, bias=self.device.DEFAULT_BIAS)
        except Exception as e:
            self.device.report_error(e)
            return
        self.update_mag_calib()              

    def update_properties(self):
        """
        Update all the displayed settings
        """
        self.update_accel_calib()
        self.update_gyro_calib()
        self.update_mag_calib()

    def notify_opened(self):
        self.update_properties()

    def calib_to_matrix(self, calib: list[float]):
        """Helper function to transform the 1D matrix into a list of [row][col]"""
        matrix = [[0.0]*3 for _ in range(3)]
        for i in range(9):
            col = i % 3
            row = int(i / 3)
            matrix[row][col] = calib[i]
        return matrix
    
    def delete(self):
        if self.gradient_descent_wizard is not None:
            self.gradient_descent_wizard.delete()
            self.gradient_descent_wizard = None
        super().delete()

def gradient_descent_thread( gradient: ThreespaceGradientDescentCalibration, 
                                samples: np.ndarray[float], origin: np.ndarray[float], 
                                params_output: list[float], **kwargs):
    #This function is just so the return value can be gotten from the function when threading
    result = gradient.calculate(samples, origin, **kwargs)
    params_output.extend(result.tolist())

@dataclass
class CalibrationResult:

    @dataclass
    class Calibration:
        bias: list[float]
        mat: list[float]

    accels: dict[int, Calibration] = field(default_factory=dict)
    mags: dict[int, Calibration] = field(default_factory=dict)

class GradientDescentCalibrationWizard:
    MIN_ODR = 500               #If any component has an ODR less then this value when starting calibration, it will be set to this

    READINGS_PER_SAMPLE = 100   #Number of readings to take before each sample
    SAMPLE_INTERVAL = 0.001     #In seconds, the time in between each reading

    CONFIGURING = 0
    GATHERING = 1
    CALCULATING = 2

    def __init__(self, device: ThreespaceDevice, on_completion: Callable[[bool],None]):
        """
        Params
        ------
        on_completion : Callback called when wizard completes or is cancelled. If cancelled, passed False, if completed, passed True
        """
        self.device = device
        try:
            accels = device.get_available_accels()
            mags = device.get_available_mags()
        except Exception as e:
            self.device.report_error(e)
            on_completion(False)
            return

        self.result: CalibrationResult|None = None

        self.completion_callback = on_completion

        self.texture_width = 400
        self.texture_height = 400
        self.sensor_obj = GlOrientationViewer(obj_lib.MiniSensorObj, GL_Renderer.text_renderer, GL_Renderer.base_font,
                                                    self.texture_width, self.texture_height, tl_arrows=False)
        self.sensor_obj.set_distance(Z_DIST)
        self.sensor_texture = TextureRenderer(self.texture_width, self.texture_height)
        with dpg.texture_registry() as self.gradient_registry:
            self.texture = dpg.add_raw_texture(width=self.texture_width, height=self.texture_height, default_value=[],  format=dpg.mvFormat_Float_rgba)

        self.accel_checkboxes = []
        self.mag_checkboxes = []
        self.cur_step_text = None
        with dpg.window(modal=True, no_move=False, no_resize=True, label="Gradient Descent Config", no_close=True, autosize=True) as self.modal:
            dpg.add_text("Select components to calibrate:")
            with dpg.table():
                dpg.add_table_column(label="Accels")
                dpg.add_table_column(label="Mags")
                with dpg.table_row():
                    with dpg.child_window(height=100) as accel_scrollview:
                        for accel in accels:
                            self.accel_checkboxes.append(dpg.add_checkbox(label=f"accel{accel}", default_value=True, user_data=accel))
                    with dpg.child_window(height=100) as mag_scrollview:
                        for mag in mags:
                            self.mag_checkboxes.append(dpg.add_checkbox(label=f"mag{mag}", default_value=True, user_data=mag))
            with dpg.group(horizontal=True):
                dpg.add_button(label="Start", callback=self.__on_config_start_button)
                dpg.add_button(label="Cancel", callback=self.__on_config_cancel_button)
        
        with dpg.handler_registry() as self.keyboard_handler:
            dpg.add_key_press_handler(dpg.mvKey_Return, callback=self.__on_keyboard_next_pressed)
            dpg.add_key_press_handler(dpg.mvKey_Spacebar, callback=self.__on_keyboard_next_pressed)

        with dpg.item_handler_registry(label="Gradient Descent Visible Handler") as self.visible_handler:
            dpg.add_item_visible_handler(callback=dpg_ext.center_window_handler_callback, user_data=self.modal)
        dpg.bind_item_handler_registry(self.modal, self.visible_handler)

        #Control variables
        self.wizard_stage = GradientDescentCalibrationWizard.CONFIGURING
        self.animating = False        
        self.__cached_accels: dict[int, int] = {}
        self.__cached_mags: dict[int, int] = {}
        self.__cached_axis_order: str = None
        self.gathering = False 
    
    def get_result(self):
        return self.result

    def __on_keyboard_next_pressed(self):
        #Gotta queue this to run in the main loop so the animations can play properly
        if self.wizard_stage == GradientDescentCalibrationWizard.CONFIGURING:
            MainLoopEventQueue.queue_event(self.__on_config_start_button)
        elif self.wizard_stage == GradientDescentCalibrationWizard.GATHERING and not self.animating:
            MainLoopEventQueue.queue_event(self.__on_next_button)

    def __on_config_cancel_button(self):
        self.delete()
        self.completion_callback(False)

    def __on_config_start_button(self):
        self.wizard_stage = None

        #Gather Selected Components
        selected_accels = []
        selected_mags = []
        for box in self.accel_checkboxes:
            if dpg.get_value(box):
                selected_accels.append(dpg.get_item_user_data(box))
        for box in self.mag_checkboxes:
            if dpg.get_value(box):
                selected_mags.append(dpg.get_item_user_data(box))

        #Nothing selected, treat it like a cancel
        if len(selected_accels) == 0 and len(selected_mags) == 0:
            self.__on_config_cancel_button()
            return

        #Configure the selected components ODRs/streaming so that the data can be quickly obtained
        self.__cached_accels = {}
        self.__cached_mags = {}

        try:
            self.__cached_accels = self.device.get_accel_odrs(*selected_accels)
            self.__cached_mags = self.device.get_mag_odrs(*selected_mags)
            self.__cached_axis_order = self.device.get_axis_order()
        except Exception as e:
            self.device.report_error(e)
            self.__on_config_cancel_button()
            return 

        #Now update the odrs for any components that need it
        try:
            new_accel_odrs = { k: 500 for k in self.__cached_accels if self.__cached_accels[k] < GradientDescentCalibrationWizard.MIN_ODR }
            if len(new_accel_odrs) > 0:
                self.device.set_accel_odrs(new_accel_odrs)
            new_mag_odrs = {k: 500 for k in self.__cached_mags if self.__cached_mags[k] < GradientDescentCalibrationWizard.MIN_ODR }
            if len(new_mag_odrs) > 0:
                self.device.set_mag_odrs(new_mag_odrs)
            
            #Change the axis order to be the required XYZ (The math would have to change without this, would rather just do this atleast for now since it is easier)
            self.device.set_axis_order("xyz")
        except Exception as e:
            self.device.report_error(e)
            self.__on_config_cancel_button()
            return
        
        #Now configure the streaming
        err = False
        for accel in self.__cached_accels:
            if not self.device.register_streaming_command(self, StreamableCommands.GetRawAccelVec, param=accel, immediate_update=False):
                err = True
                break
        for mag in self.__cached_mags:
            if not self.device.register_streaming_command(self, StreamableCommands.GetRawMagVec, param=mag, immediate_update=False):
                err = True
                break
        
        if err:
            self.device.unregister_all_streaming_commands_from_owner(self, immediate_update=True)
            Logger.log_error(f"Failed to register required commands for calibration of {self.device.name}")
            self.__on_config_cancel_button()
            return

        #Can only get samples at the slowest speed of required components
        min_hz = max(min(*self.__cached_accels.values(), *self.__cached_mags.values()), 500)

        self.device.register_streaming_callback(self.__on_sample_received, min_hz)
        self.device.update_streaming_settings()

        #Switch the window style to the gradient descent gathering
        dpg.configure_item(self.modal, label="Gradient Descent")
        dpg.delete_item(self.modal, children_only=True)
        dpg.push_container_stack(self.modal)
        dpg.add_image(self.texture, width=self.texture_width, height=self.texture_height)
        dpg.add_text("Put the sensor in the depicted orientation and press Next.", wrap=self.texture_width)
        with dpg.group(horizontal=True):
            dpg.add_text("Step")
            self.cur_step_text = dpg.add_text(" 1")
            dpg.add_text("of")
            dpg.add_text("24")
            self.back_button = dpg.add_button(label="Back", callback=self.__on_back_button)
            self.next_button = dpg.add_button(label="Next", callback=self.__on_next_button)
            dpg.add_button(label="Close", callback=self.__on_config_cancel_button)
        dpg.pop_container_stack()

        #Create variables for processing the calibration
        self.current_step = 1

        #Orientation Roots stores the root points to start rotating from in 2 Axis form
        #The first axis is which way the sensors natural Y axis should be pointing
        #The second axis is which way the sensors natural Z axis should be pointing
        rotation_sign = -1 #1 = CCW, -1 = CW
        orientation_roots = [
            [( 0, 1,  0), ( 0,  0,  1)],
            [( 0, 0, -1), (-1,  0,  0)],
            [( 0, 1,  0), ( 0,  0, -1)],
            [( 1, 0,  0), ( 0, -1,  0)],
            [( 0, 0,  1), ( 0,  1,  0)],
            [( 0, -1,  0), ( 1,  0,  0)]
        ]
        
        self.orientations = []
        for root in orientation_roots:
            forward_vec = root[1]
            down_vec = [-v for v in root[0]]
            quat = quaternion.quat_from_two_vectors(forward_vec, down_vec)
            self.orientations.append(np.array(quat, dtype=np.float64))
            rotation = quaternion.quat_from_axis_angle([0, 0, 1], math.radians(90 * rotation_sign))
            for _ in range(3):
                next = quaternion.quat_mul(self.orientations[-1], rotation) #Get the other 3 quats for this basis
                self.orientations.append(np.array(next, dtype=np.float64))
            rotation_sign *= -1 #Rotation direction is alternated to prevent the cable from winding up
        
        #Negating just this orientation to make the animation go the direction I want
        self.orientations[16] = [-v for v in self.orientations[16]]
        self.transition_time = 0.5

        self.accel_samples = { k : [] for k in selected_accels }
        self.mag_samples = { k : [] for k in selected_mags }

        self.render_quat([0, 0, 0, 1])
        self.wizard_stage = GradientDescentCalibrationWizard.GATHERING

    def animate_transition(self, quat: list[float]):
        self.animating = True
        dpg.disable_item(self.back_button)
        dpg.disable_item(self.next_button)

        start_quat = gl_space_to_sensor_quat(self.sensor_obj.orientation)
        start_time = time.time()
        elapsed_time = time.time() - start_time
        while elapsed_time < self.transition_time:
            new_quat = quaternion.slerp(start_quat, quat, elapsed_time / self.transition_time)
            new_quat = vector.vec_normalize(new_quat)
            self.render_quat(new_quat)
            dpg.render_dearpygui_frame()
            elapsed_time = time.time() - start_time
        self.render_quat(quat)

        dpg.enable_item(self.back_button)
        dpg.enable_item(self.next_button)
        self.animating = False

    def render_quat(self, quat: list[float]):
        self.sensor_obj.set_orientation_quat(gl_sensor_to_gl_quat(quat))
        with self.sensor_texture:
            self.sensor_obj.render()
        texture = np.flip(self.sensor_texture.get_texture_pixels(), 0)
        dpg.set_value(self.texture, texture.flatten())

    def __on_sample_received(self, status: ThreespaceStreamingStatus):
        if not self.gathering: return
        if status == ThreespaceStreamingStatus.Data:
            for accel in self.accel_samples:
                self.accel_totals[accel] += np.array(self.device.get_streaming_value(StreamableCommands.GetRawAccelVec, accel), dtype=np.float64)
            for mag in self.mag_samples:
                self.mag_totals[mag] += np.array(self.device.get_streaming_value(StreamableCommands.GetRawMagVec, mag), dtype=np.float64)
            self.num_readings += 1
        elif status == ThreespaceStreamingStatus.DataEnd:
            pass
        elif status == ThreespaceStreamingStatus.Reset:
            self.device.unregister_all_streaming_commands_from_owner(self)
            self.__on_config_cancel_button()

    def __gather_sample(self):
        self.accel_totals = { k : np.array([0, 0, 0], dtype=np.float64) for k in self.accel_samples }
        self.mag_totals = { k : np.array([0, 0, 0], dtype=np.float64) for k in self.mag_samples }

        self.device.update() #To remove any old readings
        self.num_readings = 0
        
        #Wait for getting atleast READINGS_PER_SAMPLE readings
        self.gathering = True
        while self.num_readings < GradientDescentCalibrationWizard.READINGS_PER_SAMPLE: #Could potentially read a bit more then num_readings, just depends on timing
            self.device.update() #Update the streaming until got all the readings
        self.gathering = False

        #Average it and append
        for accel in self.accel_totals:
            self.accel_samples[accel].append(self.accel_totals[accel] / self.num_readings)
        for mag in self.mag_totals:
            self.mag_samples[mag].append(self.mag_totals[mag] / self.num_readings)
    
    def __set_loading_window(self):
        #Setup loading window
        dpg.delete_item(self.modal, children_only=True)
        dpg.push_container_stack(self.modal)
        dpg.add_text("Calculating Calibration...")
        with dpg.table(header_row=False):
            dpg.add_table_column()
            dpg.add_table_column()
            dpg.add_table_column()
            with dpg.table_row():
                dpg.add_table_cell()
                dpg.add_loading_indicator()
        dpg.pop_container_stack()
        dpg.render_dearpygui_frame()

    def __finalize_calculation(self):
        self.wizard_stage = GradientDescentCalibrationWizard.CALCULATING
        self.__set_loading_window()
        self.result = CalibrationResult()
        gradient = ThreespaceGradientDescentCalibration(self.orientations)
        for mag in self.mag_samples:
            bias_guess = sum(self.mag_samples[mag]) / len(self.mag_samples[mag])
            self.mag_samples[mag] = [sample - bias_guess for sample in self.mag_samples[mag]]

            #Gotta thread it to allow UI to continue updating
            params = []
            thread = threading.Thread(target=gradient_descent_thread, args=(gradient, self.mag_samples[mag], self.mag_samples[mag][0], params), 
                                      kwargs = {"verbose": True}, daemon=True)
            thread.start()
            while thread.is_alive():
                dpg.render_dearpygui_frame()
            thread.join() #Should finish instantly

            params[9:] += -bias_guess #Gradient descent and this use opposite signs, so swap it
            self.result.mags[mag] = CalibrationResult.Calibration(params[9:], params[:9])
        
        for accel in self.accel_samples:
            #Gotta thread it to allow UI to continue updating
            params = []
            thread = threading.Thread(target=gradient_descent_thread, args=(gradient, self.accel_samples[accel],
                                        np.array([0, 1, 0], dtype=np.float64), params),
                                        kwargs = {"verbose": True}, daemon=True)
            thread.start()
            while thread.is_alive():
                dpg.render_dearpygui_frame()
            thread.join() #Should finish instantly
            self.result.accels[accel] = CalibrationResult.Calibration(params[9:], params[:9])

        self.delete()
        self.completion_callback(True)        

    def __on_next_button(self):
        self.__gather_sample()

        self.current_step += 1
        if self.current_step > len(self.orientations):
            self.__finalize_calculation()
            return

        dpg.set_value(self.cur_step_text, f"{self.current_step:2}")
        self.animate_transition(self.orientations[self.current_step-1])

    def __on_back_button(self):
        if self.current_step <= 1: return
        self.current_step -= 1
        dpg.set_value(self.cur_step_text, f"{self.current_step:2}")
        for samples in self.accel_samples.values():
            samples.pop(-1)
        for samples in self.mag_samples.values():
            samples.pop(-1)
        self.animate_transition(self.orientations[self.current_step-1])

    def delete(self):
        self.sensor_obj.delete()
        self.sensor_texture.destroy()

        try:
            #Stop streaming
            self.device.unregister_streaming_callback(self.__on_sample_received)
            self.device.unregister_all_streaming_commands_from_owner(self)

            #Restore ODRs that were below the minimum
            restored_accel_odrs = { k : v for k, v in self.__cached_accels.items() if v < GradientDescentCalibrationWizard.MIN_ODR }
            if len(restored_accel_odrs) > 0:
                self.device.set_accel_odrs(restored_accel_odrs)
            restored_mag_odrs = { k : v for k, v in self.__cached_mags.items() if v < GradientDescentCalibrationWizard.MIN_ODR }                
            if len(restored_mag_odrs) > 0:
                self.device.set_mag_odrs(restored_mag_odrs)

            #Restore axis order
            if self.__cached_axis_order is not None:
                self.device.set_axis_order(self.__cached_axis_order)
        except Exception as e:
            self.device.report_error(e)

        dpg.delete_item(self.gradient_registry)
        dpg.delete_item(self.keyboard_handler)
        dpg.delete_item(self.visible_handler)
        dpg.delete_item(self.modal)

class BootloaderSettingsWindow(StagedView):

    def __init__(self, device: ThreespaceDevice):
        with dpg.stage(label="Sensor Settings Stage") as self._stage_id:
            with dpg.file_dialog(width=700, height=400, file_count=1, directory_selector=False, 
                                 callback=self.__on_firmware_file_selected, show=False, modal=True,
                                 default_path=APPLICATION_FOLDER.as_posix()) as self.firmware_selector:
                dpg.add_file_extension(".xml", custom_text="[Firmware]", color=(0, 255, 0))

            try:
                serial_number = device.get_serial_number()
                firmware_valid = device.is_firmware_valid()
                if firmware_valid:
                    firmware_valid = "Valid"
                    valid_color = theme_lib.color_green
                else:
                    firmware_valid = "Invalid"
                    valid_color = theme_lib.color_disconnect_red
                #hardware_version = device.get_hardware_version() #This is technically doable from just the serial number, but requires moving the logic of parsing the serial number off the sensor
            except Exception as e:
                device.report_error(e)
                return
            
            with dpg.child_window():
                with dpg.group(horizontal=True):
                    dpg.add_text(f"Serial#:")
                    dpg.add_text(f"0x{serial_number:016X}") 
                # with dpg.group(horizontal=True):
                #     dpg.add_text(f"Hardware Version:")
                #     dpg.add_text(hardware_version)
                with dpg.group(horizontal=True):
                    dpg.add_text("Firmware:")
                    dpg.add_text(firmware_valid, color=valid_color)
                    dpg.add_button(label="Upload Firmware", callback=lambda: dpg.show_item(self.firmware_selector))               
                dpg.add_spacer(height=12)
                dpg.add_separator()
                dpg.add_spacer(height=12)
                dpg.add_button(label="Boot Firmware", callback=self.force_boot_firmware)
                     
        self.device = device
        
    def force_boot_firmware(self):
        try:
            self.device.boot_firmware()
        except Exception as e:
            self.device.report_error(e)

    def __run_firmware_update(self, firmware_path: str):
        print("Uploading firmware:", firmware_path)
        firmware_name = pathlib.Path(firmware_path).name
        width = 400
        with dpg.window(label="Test", modal=True, no_open_over_existing_popup=False, width=width, 
                        no_close=True, no_move=True, no_resize=True) as popup_window:
            dpg.add_text(f"Uploading firmware {firmware_name}", wrap=width)
            progress_bar = dpg.add_progress_bar(default_value=0, width=-1)
            progress_text = dpg.add_text(f"{0: 3}% complete")
                
        dpg.render_dearpygui_frame() #Not sure why need to render 2 frames before the get rect works correctly, but it does need done
        dpg.render_dearpygui_frame()
        dpg_ext.center_window(popup_window)
        dpg.render_dearpygui_frame()

        firmware_uploader = self.device.get_firmware_uploader()
        firmware_uploader.set_firmware_path(firmware_path)
        def set_percent_complete(percent):
            dpg.set_value(progress_text, f"{int(percent): 3}% complete")
            percent /= 100
            dpg.set_value(progress_bar, percent)
            dpg.render_dearpygui_frame()

        firmware_uploader.set_percent_callback(set_percent_complete)
        success = True
        try:
            firmware_uploader.upload_firmware()
        except Exception as e:
            success = False
            self.device.report_error(e)

        dpg.delete_item(popup_window)

    def __on_firmware_file_selected(self, sender, app_data, user_data):
        selections: dict[str,str] = app_data["selections"]
        if len(selections) == 0: return
        file_name = list(selections.keys())[0]
        file_path = list(selections.values())[0]

        MainLoopEventQueue.queue_event(lambda: self.__run_firmware_update(file_path))

    def delete(self):
        dpg.delete_item(self.firmware_selector)
        super().delete()

class BootloaderTerminalWindow(StagedView):
    """
    Creates a terminal display visual.
    To display, must call submit and pass
    the parent container or use within a 
    context with block
    """

    def __init__(self, threespace_device: ThreespaceDevice):
        self.device = threespace_device
        with dpg.stage(label="Sensor Terminal Stage") as self._stage_id:
            self.terminal = MultilineText(max_messages=50)
            self.terminal.submit(dpg.top_container_stack())
            
            with dpg.item_handler_registry(label="Terminal Visible Handler") as self.terminal_handler:
                dpg.add_item_visible_handler(callback=self.__on_terminal_visible)

            with dpg.group(horizontal=True):
                dpg.add_text("Command:")
                self.command_input = dpg.add_input_text(width=-50, on_enter=True, callback=self.__on_send_enter_command)
                dpg.add_button(label="Send", callback=self.__on_send_command)
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_text("Port:")
                dpg.add_text(str(self.device.com_port))

            #Visible Handler doesn't work on the window, sorta dissapointing, so just use the clear button
            dpg.bind_item_handler_registry(self.terminal.clear_button, self.terminal_handler)
            self.last_data_retrieve_time = None
            self.data_timeout = 0.05
            self.data = None

    #The reason this is seperated is so focus can be returned
    #to the text box if it was triggered that way
    def __on_send_enter_command(self, sender, app_data):
        self.__on_send_command(sender, app_data)
        dpg.focus_item(self.command_input)

    def __on_send_command(self, sender, app_data):
        with dpg_lock():
            command: str = dpg.get_value(self.command_input)
            self.terminal.add_message(command)
            dpg.set_value(self.command_input, "")

        try:
            command = command.encode()
            self.device.send_raw_data(command)
        except Exception as e:
            self.device.report_error(e)

    def __read_terminal(self):
        data = self.device.read_com_port(decode=False)
        if len(data) > 0:
            self.last_data_retrieve_time = time.time()
            if self.data is None:
                self.data = data
            else:
                self.data += data

        #Because binary data with no terminator, use a time based timeout to determine when the full response is received to put on one line
        if self.last_data_retrieve_time is not None:
            if time.time() - self.last_data_retrieve_time > self.data_timeout:
                self.terminal.add_message(str(self.data))
                self.data = None
                self.last_data_retrieve_time = None

    def __on_terminal_visible(self, sender, app_data):
        """
        A polling method of reading, and manually
        waiting for newline before outputting any data.
        Also accounts for multiple newlines
        """

        #Needs to be done in the main loop to not steal responses from windows, such
        #as orientation, changing settings while shutting down
        MainLoopEventQueue.queue_event(self.__read_terminal)

    def submit(self, parent=None):
        """
        Puts the SensorWindow in the parent component,
        else creates its own window
        """
        if parent is not None:
            self.container = parent
            dpg.push_container_stack(self.container)
        else:
            self.container = dpg.add_window(label="SensorTerminalWindow", pos=(200, 200))
            dpg.push_container_stack(self.container)

        dpg.unstage(self._stage_id)
       
        dpg.pop_container_stack()

    def delete(self):
        dpg.delete_item(self.terminal_handler)
        self.terminal.destroy()
        super().delete()


from dpg_ext.dpg_path_graphs import PathSeries, PathPoint
import yostlabs.tss3.eepts as yleepts
class EeptsWindow(StagedView):

    def __init__(self, device: ThreespaceDevice):
        self.device = device
        with dpg.stage() as self._stage_id:
            with dpg.child_window(border=False, menubar=True):
                with dpg.menu_bar():
                    self.start_button = dpg.add_menu_item(label="Start", callback=self.start_mapping)
                    self.stop_button = dpg.add_menu_item(label="Stop", callback=self.stop_mapping, show=False)
                    self.clear_button = dpg.add_menu_item(label="Clear", callback=self.clear_plot)
                    self.toggle_enable_button = dpg.add_menu_item(label="Pause", callback=self.__on_pause_toggle)
                    self.tag_button = dpg.add_menu_item(label="Tag", callback=self.tag_current_point)    
                    self.config_wizard_button = dpg.add_menu_item(label="Config", callback=self.__on_config_wizard_button)
                with dpg.plot(label="EEPTS Path", width=-1, height=-1, equal_aspects=True) as self.plot:
                    #Important - There is functionality built into the legend for this type of series, so make sure to display it
                    self.x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="X", auto_fit=True)
                    with dpg.plot_axis(dpg.mvYAxis, label='Y', auto_fit=True) as self.y_axis:
                        pass

        self.path_series = PathSeries([], self.plot, self.y_axis, "EEPTS Path")

        #About the path series:
        #It converts GPS coords to X, Y points in meters. DPG stores the values in the plot as floats.
        #To avoid accuracy issues, we actually plot from (0, 0) and then map the GPS starting lat/lon to that point
        #That is why there is "rooting" going on and the X,Y on the map don't actually state the longitude and latitude.
        #Store in meters also makes it easier to have a consistent aspect ratio of 1 meter to 1 meter compared to lat/lon where
        #they don't have a consistent ratio, especially longitude with their being way more space between each degree longitude
        #when near the equator.
        #I plan to later modify just the labeling of the axes to show the latitude and longitude, while internally it is
        #still using these smaller more manageable values.

        #Because of the pausing/unpausing behavior, have to track a lot more information about the points since the GPS location
        #of the point is required to get the distance travelled between points, but also the points shown may modify themselves
        #in order to show at an offset to act as if "no distance was travelled while paused".
        #So basically, this graph shows a sum of movement in meters, and while paused, acts as if no movement is being done. The GPS
        #is still required to be used for the highest accuracy because distance changes based on lat/lon as described above.

        #Control variables for adding additional functionality such as tagging and pausing
        self.__reset_control_variables()

        self.mapping_enabled = False

    def streaming_callback(self, status: ThreespaceStreamingStatus):
        if status == ThreespaceStreamingStatus.Data:
            out = yleepts.YL_EEPTS_OUTPUT_DATA(*self.device.get_streaming_value(StreamableCommands.GetEeptsOldestStep))
            if self.last_segment is None or out.segment_count != self.last_segment.segment_count:
                self.add_point(out)
        elif status == ThreespaceStreamingStatus.DataEnd:
            pass
        elif status == ThreespaceStreamingStatus.Reset:
            self.stop_mapping()

    def __reset_control_variables(self):
        self.last_point: PathPoint = None #The unmodified point that is the result of the system running
        self.last_shown_point: PathPoint = None #The point modified via pauses and unpausing, as well as what is actually displayed
        self.root_point: PathPoint = None
        self.offset_point: PathPoint = None
        self.last_segment = None
        self.paused = False

    def start_mapping(self):
        self.clear_plot()
        self.__reset_control_variables()
        try:
            #Set settings for EEPTS here for now. Need to make a way to set this in the window soon
            self.device.stop_eepts() #Just in case was already started
            self.device.start_eepts()

            self.mapping_enabled = self.device.register_streaming_command(self, StreamableCommands.GetEeptsOldestStep, immediate_update=False)
            if not self.mapping_enabled: return
            self.device.register_streaming_callback(self.streaming_callback, hz=3) #Do not need to stream very fast for EEPTS. Just needs to be max expected steps per second
            self.device.update_streaming_settings()
        except Exception as e:
            self.stop_mapping()
            self.mapping_enabled = False
            self.device.report_error(e)
        dpg.hide_item(self.start_button)
        dpg.show_item(self.stop_button)

    def stop_mapping(self):
        try:
            self.device.unregister_streaming_command(self, StreamableCommands.GetEeptsOldestStep, immediate_update=False)
            self.device.unregister_streaming_callback(self.streaming_callback)
            self.device.update_streaming_settings()

            self.device.stop_eepts()
        except Exception as e:
            self.device.report_error(e)
        self.mapping_enabled = False
        dpg.hide_item(self.stop_button)
        dpg.show_item(self.start_button)

    def add_point(self, eepts_output: yleepts.YL_EEPTS_OUTPUT_DATA):
        segment = yleepts.Segment.from_only_output_obj(eepts_output)

        #Must store both the actual point used to compute distances, and the modified point that will be shown on the graph
        self.last_point = PathPoint(segment, self.last_segment, self.root_point)
        self.last_shown_point = PathPoint(segment, self.last_segment, self.root_point)
        
        #Treat the root as 0, 0
        if self.root_point is not None:
            self.last_shown_point.x -= self.root_point.x
            self.last_shown_point.y -= self.root_point.y

        #Treat this as the start location for the point on the graph
        if self.offset_point is not None:
            self.last_shown_point.x += self.offset_point.x
            self.last_shown_point.y += self.offset_point.y

        #Essentially root is for computing distance, while offset is for positioning where that distance should start on the graph

        if self.root_point is None:
            self.root_point = self.last_point
        
        self.last_segment = segment

        #Don't add points while paused, but do need to continue computing the last point so
        #that on unpause the correct point is used for rooting/offset
        if self.paused:
            return
        
        self.path_series.add_point(self.last_shown_point)
        dpg.fit_axis_data(self.y_axis)
        dpg.fit_axis_data(self.x_axis)
    
    def tag_current_point(self):
        if self.last_shown_point is None:
            return
        self.last_shown_point.point_color = (255, 0, 255, 70)
        self.path_series.set_dirty()
    
    def clear_plot(self):
        self.path_series.clear()
        self.root_point = None
    
    def __on_pause_toggle(self, sender, app_data, user_data):
        if not self.paused:
            self.offset_point = self.last_shown_point #Offset is a visual effect, so use the last showwn
            dpg.configure_item(sender, label="Resume")
        else:
            self.root_point = self.last_point #Root is actual distance, so use the true point
            dpg.configure_item(sender, label="Pause")
        
        self.paused = not self.paused

    def __on_config_wizard_button(self, sender, app_data, user_data):
        EeptsConfigWizard(self.device) #Becaise its modal and self deleting, no need to track it

    def delete(self):
        if self.mapping_enabled:
            self.stop_mapping()
        self.path_series.delete()
        super().delete()

class EeptsConfigWizard:

    def __init__(self, device: ThreespaceDevice):
        self.device = device
        self.wizard = DpgWizard(always_centered=True, label="EEPTS Config")
        self.base_config = EeptsBaseConfigWizardWindow(self)
        self.static_heading_config = EeptsStaticHeadingConfig(self)

        self.set_view(self.base_config)

    def set_view(self, view: StagedView):
        self.wizard.set_window(view)

    def delete(self):
        self.base_config.delete()
        self.static_heading_config.delete()
        self.wizard.delete()

class EeptsBaseConfigWizardWindow(StagedView):

    def __init__(self, wizard_parent: EeptsConfigWizard):
        self.wizard = wizard_parent

        self.motion_options = { "Walk/Run": yleepts.PresetMotionWR, "Walk/Run/Crawl": yleepts.PresetMotionWRC }
        self.hand_options = {"Disabled": yleepts.PresetHandDisabled, "Enabled": yleepts.PresetHandEnabled, "Hand Only": yleepts.PresetHandOnly}
        self.heading_options = {"Dynamic": yleepts.PresetHeadingDynamic, "Static": yleepts.PresetHeadingStatic}

        motion_modes = list(self.motion_options.keys())
        hand_modes = list(self.hand_options.keys())
        heading_modes = list(self.heading_options.keys())

        with dpg.stage() as self._stage_id:
            self.motion_mode = dpg.add_combo(label="Motions", items=motion_modes, default_value=motion_modes[0])
            self.hand_mode = dpg.add_combo(label="Handheld", items=hand_modes, default_value=hand_modes[0])
            self.heading_mode = dpg.add_combo(label="Heading Mode", items=heading_modes, default_value=heading_modes[0])
            with dpg.group(horizontal=True):
                dpg.add_button(label="Close", callback=self.__on_close)
                dpg.add_button(label="Ok", callback=self.__on_submit)
    
    def __on_close(self):
        self.wizard.delete()

    def __on_submit(self):
        motion_mode =  self.motion_options[dpg.get_value(self.motion_mode)]
        hand_mode = self.hand_options[dpg.get_value(self.hand_mode)]
        heading_mode = self.heading_options[dpg.get_value(self.heading_mode)]

        #Note: Heading must be set last
        self.wizard.device.eepts_reset_settings()
        self.wizard.device.set_settings(pts_preset_hand=hand_mode, pts_preset_motion=motion_mode, pts_preset_heading=heading_mode)

        if heading_mode == yleepts.PresetHeadingStatic:
            #Need to calibrate the static heading direction
            self.wizard.set_view(self.wizard.static_heading_config)
        else:
            self.__on_close()

class EeptsStaticHeadingConfig(StagedView):

    def __init__(self, wizard_parent: EeptsConfigWizard):
        self.wizard = wizard_parent
        with dpg.stage() as self._stage_id:
            dpg.add_text("Face north while the sensor is mounted in its static position/orientation and then press 'Ok'", wrap=400)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Close", callback=self.__on_close)
                dpg.add_button(label="Ok", callback=self.__on_submit)

    def __on_close(self):
        self.wizard.delete()

    def __on_submit(self):
        self.wizard.device.eepts_set_static_offset()
        self.__on_close()




import dearpygui.dearpygui as dpg
from dpg_ext.filtered_dropdown import FilteredDropdown

from gui.resources import theme_lib

import data_charts
from data_charts import StreamOption

from typing import Callable
import numpy as np

class SensorDataWindow:

    THEMES = None

    def __init__(self, options: list[StreamOption] = None,  default_value: str=None, max_points=500, on_option_modified: Callable[["SensorDataWindow"],None] = None):
        if SensorDataWindow.THEMES is None:
            SensorDataWindow.THEMES = [theme_lib.plot_x_line_theme, theme_lib.plot_y_line_theme, theme_lib.plot_z_line_theme, theme_lib.plot_w_line_theme]

        #Options to select from for the chart
        self.set_options(options, default_value=default_value, update_window=False)
        self.option_modfied_callback = on_option_modified

        #Helper variables
        self.opened = False

        #Chart configuration
        self.max_points = max_points
        self.vertical_line_pos: float = None
        self.pad_percent = 0.05
        self.bounds_y = data_charts.get_min_bounds_for_option(self.cur_option)

        #Chart GUI Elements
        self.text = []
        self.series = []

        #Chart Data Storage
        self.y_data: list[list] = [] #One set per series
        self.x_data: list[int] = [] #Shared x axis across all series

        with dpg.child_window() as self.window:
            #Option Selection
            self.dropdown = FilteredDropdown(items=self.keys, default_item=self.cur_axis, 
                                        width=-1, allow_custom_options=False, allow_empty=False, 
                                        callback=self._on_stream_command_changed).submit()
            
            #Text Display
            with dpg.group(horizontal=True):
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_x, show=False))
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_y, show=False))
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_z, show=False))
                self.text.append(dpg.add_text("0.00000", color=theme_lib.color_w, show=False))

                #Additional option selection information if needed
                self.param_dropdown = dpg.add_combo(items=[], default_value="", show=False, callback=self._on_stream_param_changed, width=-1)
            
            #Actual graph
            with dpg.plot(width=-1, height=-1) as self.plot:
                self.x_axis = dpg.add_plot_axis(dpg.mvXAxis)
                with dpg.plot_axis(dpg.mvYAxis) as self.y_axis:
                    self.vertical_line = dpg.add_inf_line_series(x=[])
                    dpg.bind_item_theme(self.vertical_line, theme_lib.plot_indicator_theme)
        
        self.__build_stream_window()
        self.__build_param_window()

    def add_point(self, x: float, data: int|float|list):
        """
        Called to add data points to the chart. Data should match whatever
        option is selected in the window. Must call update for added points to
        actually display.
        """
        self.x_data.append(x)
        if not isinstance(data, list): #Force data to always be a list for consistency
            data = [data]
        for i, v in enumerate(data):
            self.y_data[i].append(v)
        
        if len(self.x_data) > self.max_points:
            self.x_data.pop(0)
            for axis in self.y_data:
                axis.pop(0)

    def set_axes(self, x_axis: list, y_axis: list):
        self.x_data = x_axis
        self.y_data = y_axis

    def set_max_points(self, max_points: int):
        self.max_points = max_points

    def update(self, fix_ticks=True):
        """
        Must be called for visual updates to actually occur.
        """

        #Update Series and Display Numbers
        for i, series in enumerate(self.series):
            dpg.configure_item(series, x=self.x_data, y=self.y_data[i]) #Set the axis info
            if i < len(self.text) and len(self.y_data[i]) > 0: #Set the text above up to the last number
                dpg.set_value(self.text[i], f"{self.y_data[i][-1]: .05f}")
        
        self.__update_bounds()
        self.__fix_ticks(no_fix=not fix_ticks)

    def set_vline_pos(self, x: float):
        if self.vertical_line_pos == x: return
        if x is None: #Remove the line
            self.vertical_line_pos = None
            dpg.configure_item(self.vertical_line, x=[])
            self.set_text_values_to_head()
        else:
            if x < dpg.get_axis_limits(self.x_axis)[0]: #Only add the line if in range of the current data
                self.set_vline_pos(None)
                return
            self.vertical_line_pos = x
            dpg.configure_item(self.vertical_line, x=[x])
            self.set_text_values_at_x(x)

    def set_text_values_at_x(self, x):
        """
        Sets the text values to the values at the given x value on the graph.
        This uses the values from the series itself because its based on what is graphically shown
        rather then what is in the buffer. The user is allowed to continue adding points without rendering
        them, but the intention of this is to show the value at a point on the graph, not an arbitrary point
        in the buffer.
        """
        if len(self.series) == 0: return
        min_index = None
        max_index = None
        x_data = dpg.get_value(self.series[0])[0] #Gotta used the cache X data because if paused, the x data still updates but want to do based on what is graphed

        #Find the index of the two points this x value is between
        for i in range(len(x_data)-1):
            if x_data[i] <= x <= x_data[i+1]:
                min_index = i
                max_index = i + 1
                break
        
        #This X value was not found
        if min_index is None:
            return
        
        #Linearly interpolate between the data points based on the supplied X
        min_x = x_data[min_index]
        max_x = x_data[max_index]
        percent = (x - min_x) / (max_x - min_x)

        #Get the Y value from all the axes up to the number of available text spots, and set them
        num_axes = min(len(self.text), len(self.y_data))
        for i in range(num_axes):
            y_data = dpg.get_value(self.series[i])[1]
            min_y = y_data[min_index]
            max_y = y_data[max_index]
            y = min_y + percent * (max_y - min_y)
            dpg.set_value(self.text[i], f"{y: .05f}")

    def set_text_values_to_head(self):
        """
        Look at description for set_text_values_at_x.
        Sets the text values to the most recent point that is currently rendered,
        not the most recent point added to the data buffer.
        """
        if len(self.series) == 0: return
        x_data = dpg.get_value(self.series[0])[0]
        if len(x_data) == 0: return
        self.set_text_values_at_x(x_data[-1])      

    def set_options(self, options: list[StreamOption], default_value: str = None, update_window: bool = True):
        #Remove invalid options (Optiosn that output strings)
        self.options = {"None": None}
        if options is not None:
            options = [o for o in options if 's' not in o.info.out_format.lower()]
            self.options |= { o.display_name: o for o in options }
        self.keys: list[str] = list(self.options.keys())

        cur_axis = default_value or self.keys[0]
        if update_window:
            self.dropdown.clear_all_items()
            for key in self.keys:
                self.dropdown.add_item(key)
        self.set_option(self.options[cur_axis], update_window=update_window)

    def set_option(self, option: StreamOption, param: int = None, update_window=True):
        if option is None:
            self.cur_axis = "None"
        else:
            self.cur_axis = option.display_name
        self.cur_option = option
        self.cur_command_param = param
        self.bounds_y = data_charts.get_min_bounds_for_option(self.cur_option)

        #Don't allow a None parameter for an option that requires a parameter
        if self.cur_option is not None and self.cur_option.valid_params is not None and len(self.cur_option.valid_params) > 0:
            self.cur_command_param = self.cur_option.valid_params[0]

        if update_window:
            self.dropdown.set_value(self.cur_axis)
            self.__build_param_window()
            self.__build_stream_window()

    def get_option(self):
        return self.cur_option, self.cur_command_param  

    def is_valid_option(self, option: StreamOption):
        for o in self.options.values():
            if not isinstance(o, StreamOption): continue
            if o.cmd == option.cmd: return True
        return False

    def hide(self):
        dpg.hide_item(self.window)

    def show(self):
        dpg.show_item(self.window)

    @property
    def visible(self):
        return self.opened and dpg.is_item_shown(self.window)

    #-----------------------Private Functions--------------------------

    def __build_param_window(self):
        if self.cur_option is None or self.cur_option.valid_params is None:
            dpg.hide_item(self.param_dropdown)
            return
        else:
            valid_params = self.cur_option.valid_params
            dpg.configure_item(self.param_dropdown, items=valid_params, show=True)
            dpg.set_value(self.param_dropdown, self.cur_command_param)

    def __build_stream_window(self):
        """Using current state, rebuild the plot window to be for the current state"""
        num_out = 0 if self.cur_option is None else self.cur_option.info.num_out_params

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
        self.x_data = [] #Doing this instead of clear to allow working with numpy arrays when set_axes is used
        self.y_data = []
        dpg.push_container_stack(self.y_axis)
        self.vertical_line = dpg.add_inf_line_series(x=[])
        dpg.bind_item_theme(self.vertical_line, theme_lib.plot_indicator_theme)
        for i in range(num_out):
            self.y_data.append([])
            self.series.append(dpg.add_line_series(self.x_data, self.y_data[i], label=f"{i}"))
            if i < len(SensorDataWindow.THEMES):
                dpg.bind_item_theme(self.series[-1], SensorDataWindow.THEMES[i])
        dpg.pop_container_stack()

    def __update_bounds(self):
        if isinstance(self.y_data, np.ndarray):
            max_y = np.max(self.y_data)
            min_y = np.min(self.y_data)
        else:
            max_y = max(max(data) for data in self.y_data)
            min_y = min(min(data) for data in self.y_data)
        
        #Clamp the max and min range
        if self.bounds_y[1] is not None:
            max_y = max(self.bounds_y[1], max_y)
        if self.bounds_y[0] is not None:
            min_y = min(self.bounds_y[0], min_y)

        padding = (max_y - min_y) * self.pad_percent
        min_y -= padding
        max_y += padding

        dpg.fit_axis_data(self.x_axis)
        dpg.set_axis_limits(self.y_axis, min_y, max_y)  

        #Remove the vertical line if it went out of bounds
        min_x = self.x_data[0]
        if self.vertical_line_pos is not None and min_x > self.vertical_line_pos:
            self.set_vline_pos(None)  

    def __fix_ticks(self, no_fix=False):
        if len(self.x_data) != self.max_points or no_fix:
            dpg.reset_axis_ticks(self.x_axis) #Allow ticks to be automatically handled when not at max points
            return
        #Once at max points, sometimes DPG will flash between using whole and half second intervals. To avoid this, control the ticks manually.
        #This makes the ticks only show in full seconds
        min_x_tick = int(self.x_data[0]) #Exclusive
        max_x_tick = int(self.x_data[-1]) #Inclusive
        axis_ticks = list(range(min_x_tick + 1, max_x_tick + 1))
        axis_ticks = tuple([(str(v), v) for v in axis_ticks])
        dpg.set_axis_ticks(self.x_axis, axis_ticks)
    
    #--------------------------Events-------------------------------------
    def _on_stream_param_changed(self, sender, app_data):
        self.cur_command_param = int(app_data)
        if self.option_modfied_callback:
            self.option_modfied_callback(self)

    def _on_stream_command_changed(self, sender, app_data):
        if app_data == self.cur_axis: return #It didn't change
        self.cur_axis = app_data
        self.cur_option = self.options[self.cur_axis]
        self.bounds_y = data_charts.get_min_bounds_for_option(self.cur_option)
        self.cur_command_param = None
        if self.cur_option is not None and self.cur_option.valid_params is not None and len(self.cur_option.valid_params) > 0:
            self.cur_command_param = self.cur_option.valid_params[0]
        self.__build_param_window()
        self.__build_stream_window()

        if self.option_modfied_callback:
            self.option_modfied_callback(self)

    def clear_chart(self):
        self.x_data = []
        for i, series in enumerate(self.series):
            self.y_data[i] = []
            dpg.configure_item(series, x=self.x_data, y=self.y_data[i])

    def notify_open(self):
        self.opened = True

    def notify_closed(self, *args):
        self.opened = False

    def destroy(self):
        self.dropdown.delete()
        dpg.delete_item(self.window)

#This version of the data window takes a ThreespaceDevice and manages setting up streaming and displaying streaming results,
#while providing configuration for pausing and such
from devices import ThreespaceDevice, ThreespaceStreamingStatus, StreamableCommands
class SensorDataWindowAsync(SensorDataWindow):

    X_SOURCE_TIMESTAMP = 0
    X_SOURCE_HEADER_TIMESTAMP = 1
    X_SOURCE_INDEX = 2

    def __init__(self, device: ThreespaceDevice, options: list[StreamOption] = None,  default_value: str=None, max_points=500):
        if options is None:
            options = data_charts.get_all_options_from_device(device)

        super().__init__(options, default_value=default_value, max_points=max_points)

        self.device = device

        #Streaming info
        self.streaming_hz = 100
        self.streaming = False
        self.paused = False

        #For keeping the timestamp from wrapping and controlling its source
        self.x_source = self.X_SOURCE_TIMESTAMP
        self.last_timestamp = None
        self.timestamp_offset = 0

        #Index based X Axis
        self.cur_index = 0

        #Used for speed optimization by the parent window
        self.__delay_registration = False

    def set_pause_state(self, paused: bool):
        self.paused = paused

    def delay_streaming_registration(self, delay: bool):
        self.__delay_registration = delay

    def start_data_chart(self):
        if self.streaming or self.cur_option is None: return #Already streaming or nothing to stream
        if not self.visible: return #The window isn't available for streaming

        try:
            #Y Source
            success = self.device.register_streaming_command(self, self.cur_option.cmd, self.cur_command_param, immediate_update=False)
            if not success: return

            #X Source
            success = self.device.register_streaming_command(self, StreamableCommands.GetTimestamp, immediate_update=False) #Used for the X axis
            if success:
                self.x_source = self.X_SOURCE_TIMESTAMP
            elif self.device.get_cached_header().timestamp_enabled:
                self.x_source = self.X_SOURCE_HEADER_TIMESTAMP
            else:
                self.x_source = self.X_SOURCE_INDEX

            self.clear_chart()
            if not self.__delay_registration:
                self.device.update_streaming_settings()
            self.device.register_streaming_callback(self.streaming_callback, hz=self.streaming_hz)
            self.streaming = True
            self.last_timestamp = None
            self.timestamp_offset = 0
            self.cur_index = 0
        except Exception as e:
            self.streaming = False
            self.device.report_error(e)

    def stop_data_chart(self):
        if not self.streaming: return
        try:
            self.device.unregister_streaming_command(self, self.cur_option.cmd, self.cur_command_param, immediate_update=not self.__delay_registration)
            if self.x_source == self.X_SOURCE_TIMESTAMP:
                self.device.unregister_streaming_command(self, StreamableCommands.GetTimestamp, immediate_update=not self.__delay_registration)
            self.device.unregister_streaming_callback(self.streaming_callback)
        except Exception as e:
            self.device.report_error(e)
        self.streaming = False

    def update(self, fix_ticks=True):
        if self.paused: return
        return super().update(fix_ticks=fix_ticks)
    
    def hide(self):
        super().hide()
        self.stop_data_chart()

    def show(self):
        super().show()
        self.start_data_chart()

    def streaming_callback(self, status: ThreespaceStreamingStatus):
        if status == ThreespaceStreamingStatus.Data:
            if not self.streaming: return
            data = self.device.get_streaming_value(self.cur_option.cmd, self.cur_command_param)

            #Get X from dynamic timestamp source
            if self.x_source in (self.X_SOURCE_HEADER_TIMESTAMP, self.X_SOURCE_TIMESTAMP):
                if self.x_source == self.X_SOURCE_TIMESTAMP:
                    timestamp = self.device.get_streaming_value(StreamableCommands.GetTimestamp)
                else:
                    timestamp = self.device.get_streaming_last_response().header.timestamp
                    if timestamp is None: #Something disabled the header timestamp without notifying the data charts
                        self.stop_data_chart()
                        return
        
                #Handle Wrapping of timestamp
                if self.last_timestamp is not None and timestamp < self.last_timestamp:
                    if self.last_timestamp < 0xFFFFFFFF:
                        self.timestamp_offset += 0xFFFFFFFF #U32 timestamp wrap
                    else:
                        self.timestamp_offset += 0xFFFFFFFFFFFFFFFF #U64 timestamp wrap
                self.last_timestamp = timestamp
                timestamp += self.timestamp_offset
                x = timestamp / 1_000_000
            else:
                x = self.cur_index
                self.cur_index += 1

            self.add_point(x, data)
        elif status == ThreespaceStreamingStatus.DataEnd:
            self.update(fix_ticks=self.x_source != self.X_SOURCE_INDEX)
        elif status == ThreespaceStreamingStatus.Reset:
            self.stop_data_chart()

    def _on_stream_command_changed(self, sender, app_data):
        if app_data == self.cur_axis: return #It didn't change
        self.stop_data_chart()
        super()._on_stream_command_changed(sender, app_data)
        self.start_data_chart()

    def _on_stream_param_changed(self, sender, app_data):
        super()._on_stream_param_changed(sender, app_data)
        self.stop_data_chart()
        self.start_data_chart()

    def notify_open(self):
        super().notify_open()
        self.start_data_chart()
    
    def notify_closed(self, *args):
        super().notify_closed(*args)
        self.stop_data_chart()

    def destroy(self):
        self.stop_data_chart()
        return super().destroy()
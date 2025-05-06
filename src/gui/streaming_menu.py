from typing import Callable

from devices import ThreespaceDevice, ThreespaceStreamingOption
import data_charts

import dearpygui.dearpygui as dpg
from dpg_ext.filtered_dropdown import FilteredDropdown

from utility import Logger

class StreamingOptionSelectionMenu:

    def __init__(self, sensor: ThreespaceDevice = None, max_options=16, on_modified_callback: Callable[["StreamingOptionSelectionMenu"],None]=None):
        self.device = sensor
        self.max_options = max_options
        self.callback = on_modified_callback
        
        if sensor is not None:
            self.valid_options = data_charts.load_sensor_options(sensor)
        else:
            self.valid_options = data_charts.get_all_stream_options()

        self.options: list[StreamingOptionMenu] = []
        with dpg.child_window(border=False, auto_resize_y=True) as self.window:
            self.options.append(StreamingOptionMenu(0, valid_options=self.valid_options, callback=self.__on_option_changed))

    @property
    def name(self):
        return "?" if self.device is None else self.device.name

    def __on_option_changed(self, sender: "StreamingOptionMenu", option: ThreespaceStreamingOption):
        if option.cmd is None and len(self.options) > 1 and sender != self.options[-1]:
            #Remove this option from the list of options
            self.remove_option(sender)
        elif sender == self.options[-1] and len(self.options) < self.max_options and option.cmd is not None:
            #Add another option selector!
            self.add_option_selector()
        if self.callback is not None:
            self.callback(self)

    def overwrite_options(self, options: list[ThreespaceStreamingOption]):
        self.clear_options()
    
        #Should always be at least 1 selector
        self.add_option_selector()
        for option in options:
            response = self.options[-1].set_option(option)
            if response == StreamingOptionMenu.INVALID_CMD:
                Logger.log_warning(f"Trying to apply invalid cmd {option.cmd.name} to {self.name}")
            elif response in (StreamingOptionMenu.INVALID_PARAM, StreamingOptionMenu.MISSING_PARAM):
                Logger.log_warning(f"Applying cmd {option.cmd.name} to {self.name} with invalid param {option.param}")
                self.options[-1].set_option(option, validate_param=False, empty_param=True) #Add the option and have the param empty to signify it is wrong
            
            #When set_option succeeds, the __on_option_changed callback will occur. That will create the next option_selector for this to use
            #which is why there is no add_option being called here.
        
        #Call this at the end just in case no options were supplied.
        #This will normally trigger due to the __on_option_changed callback when setting each option. But if no options
        #are supplied, this will just act as a clear and the callback would be missed. So just call again at the end anyways
        if self.callback:
            self.callback(self)

    def get_options(self) -> list[ThreespaceStreamingOption]:
        options = []
        for menu in self.options:
            option = menu.get_streaming_option()
            if option.cmd is None: break #Reached the end since a None is always shown and can't appear in the middle
            options.append(option)
        return options

    def add_option_selector(self):
        dpg.push_container_stack(self.window)
        new_menu = StreamingOptionMenu(len(self.options), valid_options=self.valid_options, callback=self.__on_option_changed)
        self.options.append(new_menu)
        dpg.pop_container_stack()
        return new_menu

    def remove_option(self, option_menu: "StreamingOptionMenu"):
        add_new_none = len(self.options) == self.max_options and self.options[-1].get_streaming_option().cmd is not None
        removal_index = option_menu.option_index
        self.options.pop(removal_index)
        option_menu.delete()
        for i in range(removal_index, len(self.options)):
            self.options[i].set_index_number(i)
        
        if add_new_none:
            self.add_option_selector()

    def clear_options(self):
        for menu in self.options:
            menu.delete()
        self.options.clear()

    def delete(self):
        for menu in self.options:
            menu.delete()
        dpg.delete_item(self.window)


class StreamingOptionMenu:

    VALID_OPTION = 0
    INVALID_CMD = 1
    INVALID_PARAM = 2
    MISSING_PARAM = 3

    def __init__(self, option_index: int, valid_options: list[data_charts.StreamOption], 
                 initial_option: ThreespaceStreamingOption = ThreespaceStreamingOption(None, None),
                 callback: Callable[["StreamingOptionMenu", ThreespaceStreamingOption],None] = None):
        self.valid_options = valid_options
        self.option_index = option_index
        self.callback = callback

        #Modify these dicts just to make it easier to access by key/enum
        self.enum_options = {o.cmd_enum : o for o in self.valid_options}
        self.options = {o.display_name : o for o in self.valid_options}
        new_options = {"None": None}
        new_options.update(self.options)
        self.options = new_options

        self.keys = list(self.options.keys())

        self.current_param_selector = None

        with dpg.group(horizontal=True) as self.group:
            self.index_text = dpg.add_text(f"{self.option_index+1:2}:")
            default_item = "None" if initial_option.cmd is None else self.enum_options[initial_option.cmd].display_name
            self.dropdown = FilteredDropdown(items=self.keys, default_item=default_item, 
                                width=450, allow_custom_options=False, allow_empty=False,
                                callback=self.__on_item_selected)
            self.dropdown.submit()
            self.param_input = dpg.add_input_text(decimal=True, auto_select_all=True, show=False, default_value=0, width=50)
            self.param_combo = dpg.add_combo(items=[], width=50, show=False, callback=self.__on_param_changed)
            with dpg.item_handler_registry() as self.edited_handler:
                dpg.add_item_deactivated_after_edit_handler(callback=self.__on_param_changed)
            dpg.bind_item_handler_registry(self.param_input, self.edited_handler)
    
    def __on_item_selected(self, sender, app_data):
        cmd_option = self.options[app_data]

        if cmd_option is not None and cmd_option.param_type is not None:
            param = 0
            if cmd_option.valid_params is not None:
                param = cmd_option.valid_params[0]
            self.__set_param(cmd_option, param)
        else:
            self.__set_param(cmd_option, None)
        
        if self.callback:
            self.callback(self, self.get_streaming_option())
    
    def __on_param_changed(self, sender, app_data, user_data):
        if self.callback:
            self.callback(self, self.get_streaming_option())

    def set_option(self, option: ThreespaceStreamingOption, validate_param=True, empty_param=False):
        """
        Returns False if the given option is not considered valid by the options provided to
        this menu
        """
        if option is None or option.cmd is None:
            self.dropdown.set_value("None")
            self.__on_item_selected(self, "None")
            return self.VALID_OPTION
        
        try:
            stream_option = self.enum_options[option.cmd]
        except:
            return self.INVALID_CMD #This option does not exist
        
        if validate_param:
            limited_params = stream_option.valid_params is not None

            if stream_option.param_type is not None:
                if option.param is None: #Can't have a None parameter for a setting that has a type
                    return self.MISSING_PARAM
                if limited_params and option.param not in stream_option.valid_params: #Can't have an invalid param for a setting that has its valid params known
                    return self.INVALID_PARAM
        
        #This option is valid, so now set it
        self.dropdown.set_value(stream_option.display_name)
        self.__on_item_selected(self, stream_option.display_name)
        if empty_param:
            self.__set_param(stream_option, "")
        elif validate_param:
            self.__set_param(stream_option, option.param)
        return self.VALID_OPTION

    def __set_param(self, stream_option: data_charts.StreamOption, param):
        dpg.hide_item(self.param_combo)
        dpg.hide_item(self.param_input)
        self.current_param_selector = None
        if param is None or stream_option.param_type is None: #Done, just had to cleanup!
            return
        
        if stream_option.valid_params is not None:
            dpg.configure_item(self.param_combo, items=stream_option.valid_params, show=True)
            dpg.set_value(self.param_combo, param)
            self.current_param_selector = self.param_combo
        else:
            dpg.set_value(self.param_input, param)
            dpg.show_item(self.param_input)
            self.current_param_selector = self.param_input
        
    def get_streaming_option(self):
        option = self.options[self.dropdown.get_value()]
        if option is None:
            return ThreespaceStreamingOption(None, None)
        cmd = option.cmd_enum
        param = None
        if self.current_param_selector is not None:
            param = dpg.get_value(self.current_param_selector)
            try:
                param = int(param)
            except: param = None
        return ThreespaceStreamingOption(cmd, param)
    
    def set_index_number(self, index: int):
        self.option_index = index
        dpg.set_value(self.index_text, f"{self.option_index + 1:2}:")
    
    def delete(self):
        self.dropdown.delete()
        dpg.delete_item(self.group)
        dpg.delete_item(self.edited_handler)
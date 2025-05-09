import dataclasses
from utility import PropertyDict
from managers.resource_manager import *
import dearpygui.dearpygui as dpg
from yostlabs.tss3.utils.streaming import ThreespaceStreamingOption, StreamableCommands

LOG_SETTINGS_KEY = "log_settings"

@dataclasses.dataclass
class LogSettings(PropertyDict):
    """
    Data binding class for the logging settings and ability to save to file
    """

    MODE_BINARY = 0
    MODE_ASCII = 1

    DEFAULT_OUTPUT_DIRECTORY = PLATFORM_FOLDERS.user_documents_path / "TSS_Suite" / "log_data"

    slot_configuration: dict[str,list[ThreespaceStreamingOption]] = dataclasses.field(default_factory=lambda: {"general": []})
    output_directory: pathlib.Path = DEFAULT_OUTPUT_DIRECTORY
    
    def __post_init__(self):
        with dpg.value_registry() as self.__registry:
            self._value_header_status = dpg.add_bool_value(default_value=False)
            self._value_header_timestamp = dpg.add_bool_value(default_value=False)
            self._value_header_echo = dpg.add_bool_value(default_value=True)
            self._value_header_checksum = dpg.add_bool_value(default_value=True)
            self._value_header_serial = dpg.add_bool_value(default_value=False)
            self._value_header_length = dpg.add_bool_value(default_value=True)

            self._value_binary_mode = dpg.add_bool_value(default_value=False)
            self._value_synchronize_timestamp = dpg.add_bool_value(default_value=False)
            self._value_log_hz = dpg.add_float_value(default_value=200)
            self._value_log_duration = dpg.add_float_value(default_value=0) #0 is forever

    def get_slots_for_serial(self, serial_number: int):
        #Default to streaming the timestamp and tared orientation if not in the dictionary yet
        #I do timestamp because it allows data charts to operate as well
        return self.slot_configuration.get(serial_number, [ThreespaceStreamingOption(StreamableCommands.GetTimestamp, None), ThreespaceStreamingOption(StreamableCommands.GetTaredOrientation, None)])

    def to_dict(self):
        base = super().to_dict()
        #Can't be a  path object
        base["output_directory"] = self.output_directory.as_posix() if isinstance(self.output_directory, pathlib.Path) else self.output_directory
        base_slots: dict[str,list[ThreespaceStreamingOption]] = {}
        for k, slots in self.slot_configuration.items():
            base_slots[k] = []
            for streaming_option in slots:
                base_slots[k].append((streaming_option.cmd.value, streaming_option.param))
        base["slot_configuration"] = base_slots
        return base

    @classmethod
    def from_dict(cls, in_dict, *args, empty_setters=False, **kwargs):
        base = super().from_dict(in_dict, *args, empty_setters=empty_setters, **kwargs)
        if not isinstance(base.output_directory, pathlib.Path): #Convert from string back to a path object
            base.output_directory = pathlib.Path(base.output_directory)
        options: dict[str,list[ThreespaceStreamingOption]] = {}
        for key, slots in base.slot_configuration.items():
            if key != "general":
                key = int(key) #When the serial number gets jsonified, it is converted to a string for some reason. Change it back
            options[key] = []
            for slot in slots:
                #options[key].append(ThreespaceStreamingOption(*slot))
                options[key].append(ThreespaceStreamingOption(StreamableCommands(slot[0]), slot[1]))
        base.slot_configuration = options
        return base

    @property
    def header_status(self):
        return dpg.get_value(self._value_header_status)
    
    @header_status.setter
    def header_status(self, value):
        dpg.set_value(self._value_header_status, value)

    @property
    def header_timestamp(self):
        return dpg.get_value(self._value_header_timestamp)
    
    @header_timestamp.setter
    def header_timestamp(self, value):
        dpg.set_value(self._value_header_timestamp, value)   

    @property
    def header_echo(self):
        return dpg.get_value(self._value_header_echo)
    
    @header_echo.setter
    def header_echo(self, value):
        dpg.set_value(self._value_header_echo, value)    

    @property
    def header_checksum(self):
        return dpg.get_value(self._value_header_checksum)
    
    @header_checksum.setter
    def header_checksum(self, value):
        dpg.set_value(self._value_header_checksum, value)    

    @property
    def header_serial(self):
        return dpg.get_value(self._value_header_serial)
    
    @header_serial.setter
    def header_serial(self, value):
        dpg.set_value(self._value_header_serial, value)    

    @property
    def header_length(self):
        return dpg.get_value(self._value_header_length)      
    
    @header_length.setter
    def header_length(self, value):
        dpg.set_value(self._value_header_length, value)  

    @property
    def binary_mode(self):
        return dpg.get_value(self._value_binary_mode)
    
    @binary_mode.setter
    def binary_mode(self, value):
        dpg.set_value(self._value_binary_mode, value)

    @property
    def synchronize_timestamp(self):
        return dpg.get_value(self._value_synchronize_timestamp)
    
    @synchronize_timestamp.setter
    def synchronize_timestamp(self, value):
        dpg.set_value(self._value_synchronize_timestamp, value)    

    @property
    def hz(self):
        return dpg.get_value(self._value_log_hz)
    
    @hz.setter
    def hz(self, value):
        dpg.set_value(self._value_log_hz, value)        

    @property
    def duration(self):
        return dpg.get_value(self._value_log_duration)     

    @duration.setter
    def duration(self, value):
        dpg.set_value(self._value_log_duration, value)             

    def delete(self):
        dpg.delete_item(self.__registry)
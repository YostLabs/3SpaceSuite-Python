"""
Used for loading in data recorded from a file, as well as store
settings that are required for interpreting raw data or the
results of reading the data.
"""

from yostlabs.tss3.api import ThreespaceHeaderInfo, ThreespaceCmdResult, ThreespaceHeader, StreamableCommands
from yostlabs.tss3.utils.streaming import ThreespaceStreamingOption, get_stream_options_from_str, stream_options_to_command
from yostlabs.tss3.utils.parser import ThreespaceBinaryParser
import yostlabs.math.vector as yl_vec

from pathlib import Path
import dataclasses
from typing import Any

import bisect
import struct

def validate_axis_order(order: str):
    valid_chars = set("-xyz")
    required_chars = set('xyz')
    order = order.lower()
    for char in order:
        if len(required_chars) == 0 or char not in valid_chars: return False #Still processing when nothing left to or an invalid character
        valid_chars.remove(char)
        if char in required_chars: required_chars.remove(char)
        if char != '-': valid_chars.add('-') #After a non -, a - is allowed again
    
    return len(required_chars) == 0

class TssCfgDict:

    def __init__(self, path: Path):
        self.comments: list[str] = []
        self.properties: dict[str,str] = {}

        if path.suffix != ".cfg":
            raise ValueError("Invalid path for a config file provided.")

        with path.open("r") as fp:
            for line in fp:
                line = line.strip()
                if line.startswith("#"): #Comment
                    self.comments.append(line)
                elif "=" in line:
                    key, value = line.split('=')
                    self.properties[key] = value
                else: continue #Blank line

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __getitem__(self, key):
        return self.properties[key]

    def __contains__(self, key):
        return key in self.properties


"""
Necessary settings for interpreting the data file
"""
@dataclasses.dataclass
class TssDataFileSettings:

    #Optional identifier
    serial_no: int|None = None

    header: ThreespaceHeaderInfo = dataclasses.field(default_factory=ThreespaceHeaderInfo)

    axis_order: str = "XYZ"
    axis_order_info: list = dataclasses.field(default_factory=list) #Handled by the post init

    data_hz: float = 200
    stream_slots: list[ThreespaceStreamingOption] = dataclasses.field(default_factory=list)
    
    def __post_init__(self):
        self.update_axis_cache()
        self.update_slot_cache()

    def update_axis_cache(self):
        self.axis_order_info = yl_vec.parse_axis_string_info(self.axis_order)

    def update_slot_cache(self):
        self.option_to_index = { option: i for i, option in enumerate(self.stream_slots) }

    @staticmethod
    def from_config_file(path: Path):
        cfg = TssCfgDict(path)
        
        settings = TssDataFileSettings()
        settings.serial_no = cfg.get("serial_number", None)
        if settings.serial_no is not None:
            settings.serial_no = int(settings.serial_no, 16) #Convert from hex to int
        
        #Axis Order
        settings.axis_order = cfg.get("axis_order", None)
        if settings.axis_order is not None:
            if not validate_axis_order(settings.axis_order): 
                settings.axis_order = None
                settings.axis_order_info = None
            else: 
                settings.axis_order_info = yl_vec.parse_axis_string_info(settings.axis_order)
        

        #Determine if the log file is from a data logger (Using logging settings)
        #or from the suite (Using streaming settings)
        from_logging = True
        for comment in cfg.comments:
            if comment.startswith("#Suite"):
                from_logging = False
                break
        
        #Header
        load_header = not from_logging
        if from_logging:
            if not "log_header_enabled" in cfg:
                load_header = False
                settings.header = None
            else:
                load_header = int(cfg["log_header_enabled"])

        if load_header:
            header_keys = ["header_status", "header_timestamp", "header_echo", "header_checksum", "header_serial", "header_length"]
            if any(k not in cfg for k in header_keys):
                settings.header = None
            else:
                settings.header.status_enabled = int(cfg["header_status"])
                settings.header.timestamp_enabled = int(cfg["header_timestamp"])
                settings.header.echo_enabled = int(cfg["header_echo"])
                settings.header.checksum_enabled = int(cfg["header_checksum"])
                settings.header.serial_enabled = int(cfg["header_serial"])
                settings.header.length_enabled = int(cfg["header_length"])
        
        #Stream Hz
        if from_logging:
            settings.data_hz = cfg.get("log_hz", None)
        else:
            settings.data_hz = cfg.get("stream_hz", None)
        if settings.data_hz is not None:
            settings.data_hz = float(settings.data_hz)
        
        #Stream Slots
        if not "stream_slots" in cfg:
            settings.stream_slots = None
        else:
            stream_string = cfg["stream_slots"]

            try:
                settings.stream_slots = get_stream_options_from_str(stream_string)
            except:
                settings.stream_slots = None
        
        return settings

def cast_via_struct_char(value: str, format):
    if format in "bBhHiIlLqQnN": #Integer types
        if value.startswith("0x"):
            value = int(value, 16)
        else:
            value = int(value)
    elif format in "efd":
        value = float(value)
    return value

from enum import Enum
@dataclasses.dataclass
class TssDataFile:
    class TimeSource(Enum):
        NONE = 0
        CMD = 1
        HEADER = 2
        MONO = 3

    path: Path

    settings: TssDataFileSettings = dataclasses.field(default_factory=TssDataFileSettings)

    def __post_init__(self):
        self.data: list[ThreespaceCmdResult] = []
        
        #A list of timestamps that indices match self.data,
        #but the time starts at 0, may be in seconds (if requested), and does not wrap.
        #This is a helper for many things that use data_files and want timestamps but don't
        #want to handle sourcing seperately from command/header or handling wrapping.
        #NOTE: This is OPTIONAL and will not be populated unless compute_monotime is called first
        self.monotime: list[float] = []

    def load_data(self):
        self.settings.update_slot_cache() #Allows faster lookup of values

        if self.path.suffix == ".csv":
            self.__load_ascii()
        elif self.path.suffix == ".bin":
            self.__load_binary()
        else:
            raise ValueError("Unknown file type")

    def __load_ascii(self):
        command = stream_options_to_command(self.settings.stream_slots) #Get the command object to figure out the data types
        
        command_out_formats = [cmd.out_format.strip('<') for cmd in command.commands if cmd is not None]
        ascii_header_format = self.settings.header.format.strip('<')
        total_format = ''.join(command_out_formats) + ascii_header_format
        total_columns = len(struct.unpack(total_format, b'\0' * struct.calcsize(total_format))) #Get num of elements in format by parsing a string that is same length as the formats size
        #Not going to use anything like pandas to load this. That would be excessive
        with self.path.open('r') as fp:
            fp.readline() #Skip the header line
            for line in fp:
                data = line.strip().split(',')
                if len(data) != total_columns:
                    raise Exception(f"Column Mismatch: {len(data)} != {total_columns}")

                #Get the header
                header_data = []
                i = 0
                for f in ascii_header_format:
                    v = cast_via_struct_char(data[i], f)
                    header_data.append(v)   
                    i += 1  
                header = ThreespaceHeader.from_tuple(tuple(header_data), self.settings.header)

                command_data = []
                #Get each commands output
                for format in command_out_formats:
                    converted_data = []
                    for f in format:
                        v = cast_via_struct_char(data[i], f)
                        converted_data.append(v)
                        i += 1
                    if len(converted_data) == 1:
                        command_data.append(converted_data[0])
                    else:
                        command_data.append(converted_data)
                self.data.append(ThreespaceCmdResult(command_data, header))

    def __load_binary(self):
        #Create the parser and load the data
        parser = ThreespaceBinaryParser()
        with self.path.open('rb') as fp:
            parser.insert_data(fp.read())

        #Configure reading the data
        parser.set_header(self.settings.header)
        parser.register_command(stream_options_to_command(self.settings.stream_slots))

        #Get all the responses
        result = parser.parse_message()
        while result is not None:
            self.data.append(result)
            result = parser.parse_message()
    
    def get_value(self, index, option: ThreespaceStreamingOption):
        return self[index].data[self.settings.option_to_index[option]]

    def get_header(self, index):
        return self[index].header

    def compute_monotime(self, divider=1, start_at_zero=True):
        """
        Must be called before get_monotime
        """
        if len(self.data) == 0: return
        self.monotime.clear()
        time_cmd = ThreespaceStreamingOption(StreamableCommands.GetTimestamp, None)
        if time_cmd in self.settings.stream_slots:
            source = TssDataFile.TimeSource.CMD 
        elif self.settings.header.timestamp_enabled:
            source = TssDataFile.TimeSource.HEADER
        else:
            return
        
        offset = 0
        last_base_time = 0
        if start_at_zero:
            offset = -self.get_time(0, source)
        for i in range(len(self.data)):
            base_time = self.get_time(i, source)
            if base_time < last_base_time:
                if last_base_time < 0xFFFFFFFF:
                    offset += 0xFFFFFFFF #U32 Header wrapping
                else:
                    offset += 0xFFFFFFFFFFFFFFFF #U64 Cmd wrapping
            final_time = base_time + offset
            if divider != 1: #The reason for the check is to prevent converting to a float in the default scenario
                final_time /= divider 
            self.monotime.append(final_time)
            last_base_time = base_time
        
    def get_monotime(self, index):
        return self.monotime[index]
    
    @property
    def has_monotime(self):
        return len(self.monotime) > 0

    def monotime_to_index(self, time: float|int, low=0, high=None):
        if high is None:
            high = len(self.monotime)
        return bisect.bisect_right(self.monotime, time, low, high) - 1

    def get_time(self, index: int, source: "TssDataFile.TimeSource"):
        if source == TssDataFile.TimeSource.CMD:
            return self.get_value(index, ThreespaceStreamingOption(StreamableCommands.GetTimestamp, None))
        elif source == TssDataFile.TimeSource.HEADER:
            return self[index].header.timestamp
        elif source == TssDataFile.TimeSource.MONO:
            return self.get_monotime(index)
        return None

    def __len__(self):
        return len(self.data)

    def __getitem__(self, key) -> ThreespaceCmdResult:
        return self.data[key]


if __name__ == "__main__":
    path = Path(r"C:\Users\YostLabs\Documents\NewTestLogLocation\2025-05-06_17-42-08\COM69\settings.cfg")

    data_file = TssDataFileSettings.from_config_file(path)

    print(data_file)



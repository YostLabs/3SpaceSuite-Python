"""
Used for loading in data recorded from a file, as well as store
settings that are required for interpreting raw data or the
results of reading the data.
"""

from yostlabs.tss3.api import ThreespaceHeaderInfo
from yostlabs.tss3.utils.streaming import ThreespaceStreamingOption, StreamableCommands, get_stream_options_from_str
import yostlabs.math.vector as yl_vec

from pathlib import Path
import dataclasses
from typing import Any

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
        self.axis_order_info = yl_vec.parse_axis_string_info(self.axis_order)

    def update_axis_cache(self):
        self.axis_order_info = yl_vec.parse_axis_string_info(self.axis_order)

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
        
        print(f"{from_logging=}")
        #HeaderC:\Users\YostLabs\Documents\NewTestLogLocation\2025-05-05_16-24-06\COM69
        load_header = not from_logging
        if from_logging:
            if not "log_header_enabled" in cfg:
                print("Not available")
                load_header = False
                settings.header = None
            else:
                load_header = int(cfg["log_header_enabled"])
                print("Available?", load_header)

        if load_header:
            print("Loading header")
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

@dataclasses.dataclass
class TssDataFile:
    path: Path

    settings: TssDataFileSettings = dataclasses.field(default_factory=TssDataFileSettings)

    def load_data(self):
        pass

    @property
    def length(self):
        return 0

    def __getitem__(self, key):
        return None


if __name__ == "__main__":
    path = Path(r"C:\Users\YostLabs\Documents\NewTestLogLocation\2025-05-06_17-42-08\COM69\settings.cfg")

    data_file = TssDataFileSettings.from_config_file(path)

    print(data_file)



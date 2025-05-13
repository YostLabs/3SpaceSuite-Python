import threading
from dpg_ext.global_lock import dpg_lock
import dataclasses

class WatchdogTimer:
    def __init__(self, on_timeout, timeout=1, ):
        """
        on_timeout: A callback function to call when the timer times out
        timeout: Time in seconds until the watchdog expires
        """
        self.on_timeout = on_timeout
        self.timeout = timeout
    
    def set_timeout(self, timeout):
        self.timeout = timeout

    def start(self):
        self.thread = threading.Timer(self.timeout, self.on_timeout)
        self.thread.setDaemon(True)
        self.thread.start()
    
    def stop(self):
        self.thread.cancel()
    
    def feed(self):
        self.stop()
        self.start()

from dpg_ext.log_window import LogWindow
import dearpygui.dearpygui as dpg
import pathlib

class Logger:
    """
    A global log manager that Log
    Windows can subscribe to to get
    updated based on this global logger.

    Not really efficient right now, but lazy and not that big of a deal for now
    """
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5

    LOG_FILE = None
    DATA_MANAGER = None

    @classmethod
    def init(cls):
        cls.log_windows: list[LogWindow] = []

        cls.buffered_messages: list[tuple[str, int]] = []


    #This is seperated out so that log files, and thus session folders, are only generated if
    #an actual data logging session takes place, not just every time the app is opened
    @classmethod
    def build_log_file(cls, folder: pathlib.Path):
        """
        Build log file and write out any cached data that was written before
        this finished initializing
        """
        if cls.LOG_FILE is not None:
            return

        path_name = folder / "log.txt"
        if not path_name.parent.exists():
            path_name.parent.mkdir(parents=True, exist_ok=True)
        cls.LOG_FILE = open(path_name, 'w')
    
    @classmethod
    def close_log_file(cls):
        if cls.LOG_FILE is None:
            return
        cls.LOG_FILE.close()
        cls.LOG_FILE = None
            
    @classmethod
    def cleanup(cls):
        if cls.LOG_FILE is not None:
            cls.LOG_FILE.close()

    @classmethod
    def connect_window(cls, window: LogWindow):
        cls.log_windows.append(window)
        if len(cls.log_windows) == 1:
            for message, level in cls.buffered_messages:
                window._log(message, level)
            cls.buffered_messages.clear()


    @classmethod
    def _log(cls, message, level):
        msg = f"{LogWindow.build_message_str(message, level)}\n"
        if cls.LOG_FILE is not None:
            cls.LOG_FILE.write(msg)
            cls.LOG_FILE.flush()
        
        if len(cls.log_windows) == 0:
            cls.buffered_messages.append((message, level))

        with dpg_lock():
            for log_window in cls.log_windows:
                log_window._log(message, level)
        print(msg, end="", flush=True)

    @classmethod
    def log(cls, message):
        cls._log(message, cls.TRACE)

    @classmethod
    def log_debug(cls, message):
        cls._log(message, cls.DEBUG)

    @classmethod
    def log_info(cls, message):
        cls._log(message, cls.INFO)

    @classmethod
    def log_warning(cls, message):
        cls._log(message, cls.WARNING)

    @classmethod
    def log_error(cls, message):
        cls._log(message, cls.ERROR)

    @classmethod
    def log_critical(cls, message):
        cls._log(message, cls.CRITICAL)

def str_to_foldername(string: str):
    """
    Given a string, replace characters that would be invalid
    in a folder name with underscores
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        string = string.replace(char, '_')
    return string

from dataclasses import dataclass
from typing import ClassVar
class GpsUtility:

    @staticmethod
    def convert_ddmm_to_d(ddmm: float):
        degrees = int(ddmm / 100)
        ddmm -= degrees * 100
        minutes = float(ddmm)
        return degrees + (minutes / 60)

    @staticmethod
    def convert_gps_lat_to_degrees(lat: str, ns: str):
        degrees = GpsUtility.convert_ddmm_to_d(float(lat))
        if ns == 'N':
            return degrees
        return -degrees
    
    @staticmethod
    def convert_gps_long_to_degrees(long: str, ew: str):
        degrees = GpsUtility.convert_ddmm_to_d(float(long))
        if ew == "E":
            return degrees
        return -degrees

    #Positioning of fields in returned messages
    @dataclass
    class GGA:
        format: ClassVar[int] = 0
        time: ClassVar[int] = 1
        lat: ClassVar[int] = 2
        ns: ClassVar[int] = 3
        long: ClassVar[int] = 4
        ew: ClassVar[int] = 5
        quality: ClassVar[int] = 6
        num_sat: ClassVar[int] = 7
        hdop: ClassVar[int] = 8
        alt: ClassVar[int] = 9
        ualt: ClassVar[int] = 10
        sep: ClassVar[int] = 11
        usep: ClassVar[int] = 12
        diff_age: ClassVar[int] = 13
        diff_station: ClassVar[int] = 14
        checksum: ClassVar[int] = 15

    @dataclass
    class RMC:
        format: ClassVar[int] = 0
        time: ClassVar[int] = 1
        status: ClassVar[int] = 2
        lat: ClassVar[int] = 3
        ns: ClassVar[int] = 4
        long: ClassVar[int] = 5
        ew: ClassVar[int] = 6
        spd: ClassVar[int] = 7
        cog: ClassVar[int] = 8
        date: ClassVar[int] = 9
        mv: ClassVar[int] = 10
        mv_ew: ClassVar[int] = 11
        pos_mode: ClassVar[int] = 12
        checksum: ClassVar[int] = 13

from typing import TypeVar, Generic, SupportsAbs, Callable, ParamSpec
P = ParamSpec('P')
T = TypeVar('T', bound=SupportsAbs[Callable])

class Callback(Generic[P, T]):

    def __init__(self):
        self.callbacks: list[Callable[P, T]] = []
        self.enabled = True

    def subscribe(self, cb: Callable[P, T], front=False):
        """
        Allows specifying order the callback should be inserted.
        This makes sense for things that logically should be resolved in the order they are created.
        For example, if you have a tree of items that require cleanup, naturally the cleanup should start
        from the leafs instead of the root
        """
        if front:
            self.callbacks.insert(0, cb)
        else:
            self.callbacks.append(cb)
    
    def unsubscribe(self, cb: Callable[P, T]):
        if cb in self.callbacks:
            self.callbacks.remove(cb)

    def disable(self):
        """
        Can be useful to disable a callback in situations
        where it would lead to circular calls.
        """
        self.enabled = False

    def _notify(self, *args, verbose=False):
        """
        Meant for use by the callback
        creator
        """
        if not self.enabled:
            return
        
        if verbose:
            print("Notifying Callbacks:", self.callbacks)
        for callback in self.callbacks:
            if verbose:
                print("Calling:", callback)
            callback(*args)

    def clear(self):
        self.callbacks.clear()

from queue import Queue
from types import FunctionType
class MainLoopEventQueue:

    sync_events: Queue[FunctionType] = Queue()
    dpg_events: Queue[FunctionType] = Queue()

    @staticmethod
    def queue_sync_event(event: FunctionType):
        MainLoopEventQueue.sync_events.put(event)

    @staticmethod
    def queue_dpg_event(event: FunctionType):
        MainLoopEventQueue.dpg_events.put(event)

    @staticmethod
    def process_sync_events():
        events = []
        while MainLoopEventQueue.sync_events.qsize() > 0:
            events.append(MainLoopEventQueue.sync_events.get(block=False))

        for event in events:
            event()

    @staticmethod
    def process_dpg_events():
        events = []
        while MainLoopEventQueue.dpg_events.qsize() > 0:
            events.append(MainLoopEventQueue.dpg_events.get(block=False))

        for event in events:
            event()

#Used to allow to_dict to also get values from @property variables
#as well as load a class from that same dict setting the associated property variables.
#It does that in addition to working with the base dictionary features from dataclasses
class PropertyDict:

    def to_dict(self):
        dict = {}
        if dataclasses.is_dataclass(self):
            dict |= dataclasses.asdict(self)
        dict |= {
            k: v.fget(self)
            for k, v in self.__class__.__dict__.items()
            if isinstance(v, property)
        }
        return dict
    
    @classmethod
    def from_dict(cls, dict: dict, *args, empty_setters=False, **kwargs):
        instance = cls(*args, **kwargs)
        instance_properties = {k: v for k, v in cls.__dict__.items() if isinstance(v, property)}
        for key, value in dict.items():
            if key in instance.__dict__:
                instance.__dict__[key] = value
            elif key in instance_properties:
                prop = instance_properties[key]
                if prop.fset is None:
                    if not empty_setters:
                        raise Exception("Attempting to create from dict with missing setter")
                    else:
                        continue
                instance_properties[key].fset(instance, value)
            else:
                raise Exception(f"Unknown dictionary element for creating {cls} from dict")
        return instance
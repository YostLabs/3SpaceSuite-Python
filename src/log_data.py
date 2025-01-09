from log_devices import LoggableDevice, ThreeSpaceLogDevice
from log_errors import LogError, ErrorLevel, ErrorLevels
from utility import Logger, Callback
import threading
import traceback
import time
import pathlib
import json
from io import TextIOWrapper
import shutil

import datetime

class LogGroup:
    """
    Base LogGroup used with the data logger
    A log group is simply a collection of LoggableDevices that handles the logic for how to obtain the data and format/output it
    to a file. For custom file formats, behavior, data combination... just create a custom LogGroup and use that with the data logger.
    """

    def setup(self, output_folder: pathlib.Path): ...
    def start(self): ...
    def stop(self): ...
    def update(self): ...

    def synchronize(self): ...

    def mark_fatal(self): ...

class DefaultLogGroup(LogGroup):
    """
    A simple collection of LoggableDevices and a group name.
    Can output either as a .CSV or raw .BIN data file.
    If CSV is set to False, the LoggableDevice must return byte-like objects in their get_data tuple
    """

    def __init__(self, devices: list[LoggableDevice], name: str, csv: bool = False):

        self.name = name
        self.devices = devices
        
        self.is_csv = csv
        self.csv_header = None

        self.file: TextIOWrapper = None
        self.file_path: pathlib.Path = None

        self.running = False

        self.highest_error_level = ErrorLevels.OK
        self.start_time = time.time()

    def setup(self, output_folder: pathlib.Path):
        if self.highest_error_level.severity >= ErrorLevels.MAJOR.severity:
            return
        
        for device in self.devices:
            device.setup()
            self.check_device_errors(device)
              
        if self.highest_error_level.severity >= ErrorLevels.MAJOR.severity:
            Logger.log_error(f"Failed to setup log group {self.name}")
            return
        
        #Create metadata files
        for device in self.devices:
            metadata = device.get_metadata()
            if metadata is not None:
                with open(output_folder / f"{self.name}.cfg", "w") as fp:
                    fp.write(metadata)

        ext = "csv" if self.is_csv else "bin"
        self.file_path = output_folder / f"{self.name}.{ext}"
        self.__initialize_file(self.file_path)
        Logger.log_info(f"Logging to {self.file_path.as_posix()}")

    def __initialize_file(self, file_path: pathlib.Path):
        if self.is_csv:
            group_labels = []
            for device in self.devices:
                device_labels = ','.join(device.get_output_names())
                group_labels.append(device_labels)
            self.csv_header = ','.join(group_labels)

        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        access_mode = "w" if self.is_csv else "wb"
        self.file = open(file_path, access_mode)

        if self.csv_header is not None:
            self.file.write(f"{self.csv_header}\n")

    def synchronize(self):
        if self.highest_error_level.severity >= ErrorLevels.MAJOR.severity:
            return
        for device in self.devices:
            device.synchronize()
            self.check_device_errors(device)
            

    def start(self):
        if self.running or self.highest_error_level.severity >= ErrorLevels.MAJOR.severity:
            return False
        self.running = True
        for device in self.devices:
            device.start()
        self.start_time = time.time()

    def stop(self):
        if not self.running:
            return False
        for device in self.devices:
            device.stop()

        self.running = False
        self.file.close()

    def mark_fatal(self):
        self.highest_error_level = ErrorLevels.FATAL

    def update(self):
        if self.highest_error_level.severity >= ErrorLevels.MAJOR.severity:
            return
        
        for device in self.devices:
            self.check_device_errors(device)

        #Gather all the new data
        while any(device.is_data_available() for device in self.devices):
            
            #Get data from main device first
            data = []
            for device in self.devices:
                data.extend(device.get_data())
            
            #Make sure the act of getting data didn't cause any errors
            for device in self.devices:
                self.check_device_errors(device)

            result = None
            #Convert to ascii
            if self.is_csv:
                for i in range(len(data)):
                    if isinstance(data[i], float):
                        data[i] = f"{data[i]:.6f}"
                    else:
                        data[i] = str(data[i])
                dataline = ','.join(data)
                result = f"{dataline}\n"
            else: #Its in binary
                result = b''.join(data)
            self.file.write(result)
    
    def check_device_errors(self, device: LoggableDevice):
        new_errors = device.get_errors()
        for error in new_errors:
            if error.level == ErrorLevels.MAJOR and time.time() - self.start_time <= 5: #Elevate major errors if within first 5 seconds
                error.level = ErrorLevels.FATAL
            if error.level.severity > self.highest_error_level.severity:
                self.highest_error_level = error.level
            if error.level == ErrorLevels.FATAL:
                raise Exception(error.msg)
            self.log_err(error)
    
    def log_err(self, error: LogError):
        if error.level == ErrorLevels.OK:
            return
        timestamp = time.time() - self.start_time
        timestamp = f"{timestamp:.2f}s"
        if error.level.severity <= ErrorLevels.MINOR.severity:
            Logger.log_warning(f"{timestamp}    {error.msg}")
        elif error.level == ErrorLevels.MAJOR:
            Logger.log_error(f"{timestamp}    {error.msg}")

from device_managers import DeviceManager
from utility import str_to_foldername
class DataLogger:

    VERSION = "V3.0"

    def __init__(self):
        #File Management
        self.on_logging_start = Callback()
        self.on_logging_stopped = Callback()
        self.on_logging_setup = Callback()
        self.on_update = Callback()

        self.log_groups = None
        self.output_path = None
        self.base_folder = None
        
        self.logging = False
        self.duration = float('inf')

        #For computing timing characteristics of the logging system
        self.__count = 0
        self.__fps = 0
        self.__start_time = 0
        self.__last_time = 0
        self.__fps_calc_interval = 0.5
        self.time_elapsed = 0

    def set_log_groups(self, log_groups: list[LogGroup]):
        if self.logging: return
        self.log_groups = log_groups
    
    def set_output_folder(self, output_folder: pathlib.Path):
        self.base_folder = output_folder

    def set_duration(self, duration: float):
        if duration == 0:
            self.duration = float('inf')
        else:
            self.duration = duration

    def is_logging(self):
        return self.logging

    def start_logging(self):
        if self.logging:
            return False
        self.logging = True

        if self.log_groups is None or self.base_folder is None:
            return False
        
        now = datetime.datetime.now()
        folder = now.strftime("%Y-%m-%d_%H-%M-%S")
        self.output_path = self.base_folder / folder
        count = 1
        while self.output_path.exists():
            modified_folder = folder + f"_{count}"
            count += 1
            self.output_path = self.base_folder / modified_folder
        

        Logger.build_log_file(self.output_path) #Ensure the logger actually writes to the file now

        try:
            for log_group in self.log_groups:
                log_group.setup(self.output_path)
            self.on_logging_setup._notify()

            for log_group in self.log_groups:
                log_group.synchronize()

            for log_group in self.log_groups:
                log_group.start()
        except Exception as e:
            Logger.log_error("Failed to start logging")
            self.stop_logging(verbose=False)

            #Cleanup the folder that was created. Don't want it since just instantly failed
            try:
                shutil.rmtree(self.output_path.as_posix())
            except Exception as e:
                Logger.log_critical("Failed to cleanup folders")
                Logger.log_critical(str(e))
        
        self.__start_time = time.time()
        self.__count = 0

        self.time_elapsed = 0
        self.on_logging_start._notify()
    
    def stop_logging(self, verbose=True):
        if not self.logging:
            return False
        self.logging = False
        self.__stop_time = time.time()
        if verbose:
            Logger.log_info(f"Logging ended after {self.__stop_time - self.__start_time:.2f} seconds")
        for log_group in self.log_groups:
            log_group.stop()
        self.__count = 0
        self.__start_time = 0
        self.__last_time = 0
        self.__fps = 0
        self.on_logging_stopped._notify()
        self.time_elapsed = 0
        Logger.close_log_file()
        return True
    
    def update(self):
        if not self.logging:
            return
        
        try:
            for log_group in self.log_groups:
                log_group.update()
            self.time_elapsed  = time.time() - self.__start_time
            self.on_update._notify(self.time_elapsed)
        except Exception as e:
            #Any exception that wasn't handled by the internal
            #error handlers, or was intentionally raised and not
            #handled from the internal log_groups, is considered
            #a fatal error.
            timestamp = time.time() - self.__start_time
            timestamp = f"{timestamp:.2f}s"
            Logger.log_critical(f"{timestamp}    Fatal Error: " + str(e))
            Logger.log(traceback.format_exc())
            Logger.log_critical(f"{timestamp}    Stopping Logging")
            
            #Ensure every log group knows it failed
            for log_group in self.log_groups:
                log_group.mark_fatal()

            self.stop_logging()
            return
        
        self.__count += 1
        cur_time = time.time()
        fps_time_elapsed = cur_time - self.__last_time
        if fps_time_elapsed > self.__fps_calc_interval:
            self.__fps = self.__count / fps_time_elapsed
            self.__last_time = cur_time
            self.__count = 0  

        if self.time_elapsed >= self.duration:
            self.stop_logging() 

    @property
    def fps(self):
        return self.__fps
        
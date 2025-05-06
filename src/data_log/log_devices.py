"""
Logic for logging. Contains LoggableDevices
and Logger logic
"""
from devices import ThreespaceDevice, ThreespaceStreamingOption, StreamableCommands, ThreespaceStreamingStatus, ThreespaceCmdResult
import yostlabs.tss3.consts as threespace_consts
from data_log.log_errors import LogError, ErrorLevel, ErrorLevels
from utility import Logger

from typing import NamedTuple, ClassVar
import time

import version

#To seperate the actual device logic from logging itself
#LoggableDevice will be applied to another layer of abstraction/decorator
#around the actual device instead of having the base device classes inherit from this
class LoggableDevice:
    """
    Required class structure for all devices that can
    be logged out to a file.
    """

    def is_data_available(self):
        """
        Returns whether or not there is data available
        to be read from this device
        """
        return True
    
    def setup(self):
        """
        Does any initialization needed to start
        that can be done before actually starting
        """

    def start(self):
        """
        Actually starts whatever processes are needed.
        Setup that isn't time dependent should go in setup, not here
        """

    def synchronize(self):
        """
        The operation that will be called on all loggable devices when attempting to synchronize
        """
    
    def stop(self):
        """
        Does any finalization needed to stop gathering log data from this device
        """

    def get_output_names(self) -> list[str]:
        """
        Return a list containing, in order, the name of
        the values that are returned by this device
        """
    
    def get_data(self) -> NamedTuple:
        """
        Return values in the order they are specified in get_output_names
        as a Tuple
        """

    def get_metadata(self) -> str:
        """
        Return a metadata string
        """
        return None


    def get_errors(self) -> list[LogError]:
        """
        Return the newest errors the device has
        """
    
    def get_highest_error(self) -> LogError:
        """
        Return the error this device had at any point
        in time with the largest severity
        """

class ThreeSpaceLogDevice(LoggableDevice):

    def __init__(self, device: ThreespaceDevice, log_options: list[ThreespaceStreamingOption], data_rate: float, binary:bool=False, sync_timestamp=True):
        self.device = device

        self.log_options = log_options
        self.labels = None
        self.data_rate = data_rate #In HZ 

        self.binary_format = binary
        self.sync_timestamp = sync_timestamp

        #Data Buffering
        self.buffer: list[ThreespaceCmdResult[list]] = []

        #This header value needs reformatted when enabled to match ASCII formatting. So cache this
        #one time to avoid repeated calls to get_index(serial)
        self.header_cached = False
        self.serial_index = None

        #Error Handling
        self.last_status = LogError(ErrorLevels.OK)
        self.highest_error = self.last_status
        self.errors = [self.last_status]
        self.new_errors = [self.last_status]
        self.device.on_error.subscribe(self.__on_connection_error, front=True)
        self.cleaned_up = False

        #Validation values
        self.last_timestamp = 0 #Timestamp from the device

    def is_data_available(self):
        return len(self.buffer) > 0

    def setup(self):
        #Ensure that nothing else is streaming. All streaming will be dedicated to logging
        success = self.device.force_reset_streaming()
        if not success:
            self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to acquire stream lock for {self.device.name}"))
            return False
        
        if len(self.log_options) == 0:
            self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to setup device {self.device.name}, no streaming commands selected"))
            return

        #Prevent streaming from auto starting until start is called
        self.device.pause_streaming(self)
        try:
            for option in self.log_options:
                success = self.device.register_streaming_command(self, option, immediate_update=False)
                if not success:
                    self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to setup device {self.device.name} when registering streaming command {option}"))
                    self.cleanup()
                    return False
            self.device.register_streaming_callback(self.streaming_callback, hz=self.data_rate)
            success = self.device.update_streaming_settings() #Now that everything has been registered, update
            if not success:
                self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to setup device {self.device.name} when registering streaming commands. Check that all commands are valid."))
                self.cleanup()
                return False
            self.labels = self.device.get_streaming_labels().split(',')
        except Exception as e:
            self.cleanup()
            self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to setup device {self.device.name}"))
            Logger.log_critical(f"{self.device.name}: {str(e)}")
        
        #Prevent modifications of streaming slots/timing while data logging is active...
        self.device.lock_streaming_modifications(self) 
        return True

    def synchronize(self):
        if not self.sync_timestamp: return
        try:
            self.device.reset_timestamp()
        except Exception as e:
            self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to synchronize device {self.device.name}"))
            Logger.log_critical(f"{self.device.name}: {str(e)}")

    def start(self):
        try:
            self.device.unlock_streaming_modifications(self)
            self.device.resume_streaming(self) #Must unlock modifications to allow resuming
            self.device.lock_streaming_modifications(self)
            self.last_timestamp = 0
            self.header_cached = False
            self.serial_index = None
            self.checksum_index = None
            self.data_length_index = None
        except Exception as e:
            self.add_error(LogError(ErrorLevels.MAJOR, f"Failed to start device {self.device.name}"))
            Logger.log_critical(f"{self.device.name}: {str(e)}")
        return True

    def stop(self):
        try:
            self.cleanup()
        except Exception as e:
            self.add_error(LogError(ErrorLevels.MINOR, f"Failed to stop device {self.device.name}"))
            Logger.log_critical(f"{self.device.name}: {str(e)}")
        return True

    def get_output_names(self) -> list[str]:
        return self.labels
    
    def get_data(self):
        if len(self.buffer) == 0:
            return None
        response = self.buffer.pop(0)
        if self.binary_format:
            return [response.raw_binary]
        
        #Get the actual data values
        header = response.header
        result = list(header.raw)
        if self.serial_index is not None:
            result[self.serial_index] = hex(result[self.serial_index])

        for data in response.data:
            if isinstance(data, list):
                result.extend(data)
            else:
                result.append(data)
        return result

    def get_metadata(self):
        serial_number = self.device.get_serial_number()
        settings = self.device.get_all_settings()
        setting_string = f"#Suite {version.get_version()}\nserial_number=0x{serial_number:x}\n"
        setting_string += '\n'.join(f"{key}={value}" for key, value in settings.items())
        return setting_string

    def get_errors(self) -> list[LogError]:
        errors = self.new_errors.copy()
        self.new_errors.clear()
        return errors

    def get_highest_error(self) -> LogError:
        """
        Return the error this device had at any point
        in time with the largest severity
        """
        return self.highest_error

    def add_error(self, error: LogError):
        self.last_status = error
        if error.level.severity > self.highest_error.level.severity:
            self.highest_error = error
        self.errors.append(error)
        self.new_errors.append(error)

    def streaming_callback(self, status: ThreespaceStreamingStatus):
        if status == ThreespaceStreamingStatus.Data:
            self.buffer.append(self.device.streaming_manager.get_last_response())
        elif status == ThreespaceStreamingStatus.DataEnd: #Only update the graph after this update of the streaming is done
            if not self.header_cached: #Cacheing is done here to try and minimize the number of calls to this if statement
                self.serial_index = self.buffer[0].header.info.get_index(threespace_consts.THREESPACE_HEADER_SERIAL_BIT)
                self.header_cached = True
        elif status == ThreespaceStreamingStatus.Reset:
            self.__on_stream_stolen()

    def __on_stream_stolen(self):
        print("Stream Stolen")
        if self.last_status.level != ErrorLevels.FATAL: #If was fatal, then the cleanup will steal the reference, don't care about this error
            self.add_error(LogError(ErrorLevels.MAJOR, msg=f"Data Stream stolen from {self.device.name}"))
        self.cleanup()
    
    def __on_connection_error(self, device, exception):
        print("Connection Error")
        self.add_error(LogError(ErrorLevels.MAJOR, msg=f"Connection Error from {self.device.name}"))

    def cleanup(self):
        if self.cleaned_up:
            return
        self.cleaned_up = True
        try:
            self.device.unlock_streaming_modifications(self)
            for option in self.log_options:
                self.device.unregister_streaming_command(self, option, immediate_update=False)
            self.device.unregister_streaming_callback(self.streaming_callback)
            self.device.update_streaming_settings()
            self.device.resume_streaming(self)
            self.device.on_error.unsubscribe(self.__on_connection_error)
        except:
            Logger.log_critical(f"{self.device.name} failed to properly close")
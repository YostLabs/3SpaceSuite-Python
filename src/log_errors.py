from dataclasses import dataclass
from typing import ClassVar

"""
Error Handling Overview:
All errors are handled during the update and internally to each log_device.
Fatal Errors are handled by the exception catching of the main update thread.

It is a requirement that setup, start, and stop can all run without error
    This is achieved by the individual log_devices handling the errors themselves. They can
    still submit errors, they just won't be processed until logging actually starts

    This is done to reduce the number of recovery provisions that need to be taken.
"""

class ErrorLevel:

    def __init__(self, severity, char_code):
        self.severity = severity
        self.char_code = char_code

@dataclass
class ErrorLevels:
    OK: ClassVar[ErrorLevel] = ErrorLevel(0, 'i')      #There is no error
    WARNING: ClassVar[ErrorLevel] = ErrorLevel(1, 'w') #Log the error, but continue as normal
    MINOR: ClassVar[ErrorLevel] = ErrorLevel(2, 'm')   #Log the error, but more severe, continue as normal
    MAJOR: ClassVar[ErrorLevel] = ErrorLevel(3, 'a')   #There was an error, just this log group should shut down
    FATAL: ClassVar[ErrorLevel] = ErrorLevel(4, 'f')   #The entire logger should stop

class LogError:

    def __init__(self, error_level: ErrorLevel, msg: str = "", status_bit: int = 0):
        """
        Error Level: Severity of the error and how to makre the file
        Msg: Error Msg
        Status Bit: What bit to mark the line in the CSV with for the error
        """
        self.msg = msg
        self.level = error_level
        self.status_bit = status_bit
"""
Includes utility for working with data charts and configuration information
for how some data will show up
"""
from dataclasses import dataclass, field
from devices import ThreespaceDevice, StreamableCommands, threespaceCommandGetInfo, ThreespaceCommandInfo
import re

@dataclass
class StreamOption:
    display_name: str

    cmd_enum: StreamableCommands = None
    cmd: ThreespaceCommandInfo = None

    param_type: type = None
    valid_params: list = None

def __get_options(streamable_commands: list[StreamableCommands]):
    options: list[StreamOption] = []
    for command in streamable_commands:
        cmd = threespaceCommandGetInfo(command.value)
        display_name = ' '.join(re.findall(r'[A-Z][a-z]*', command.name)[1:])
        options.append(StreamOption(display_name, command, cmd, get_command_param_type(command)))
    return options

def get_all_stream_options():
    return __get_options(list(StreamableCommands))

def load_sensor_options(sensor: ThreespaceDevice):
    streamable_commands = sensor.get_streamable_commands()
    options = __get_options(streamable_commands)
    load_valid_params(options, sensor)
    return options

def load_valid_params(options: list[StreamOption], sensor: ThreespaceDevice):
    for option in options:
        option.valid_params = get_valid_params(option.cmd_enum, sensor)

@dataclass
class DataChartAxisOption:
    display_name: str

    cmd_enum: StreamableCommands = None
    cmd: ThreespaceCommandInfo = None

    valid_params: list = None

    #The minimum values for the top and bottom of the chart bounds. The chart can grow outside this range, but never less then it.
    #If None, then that bound is purely automated
    bounds_y = (None, None) #Min and max bound 

def get_all_data_chart_axis_options(sensor: ThreespaceDevice):
    streamable_commands = sensor.get_streamable_commands()
    return build_all_data_chart_axis_options(streamable_commands, sensor)

def get_command_param_type(command: StreamableCommands):
    if command in (StreamableCommands.GetBarometerAltitudeById, StreamableCommands.GetBarometerPressureById):
        return int
    elif command in (StreamableCommands.GetRawAccelVec, StreamableCommands.GetCorrectedAccelVec, StreamableCommands.GetNormalizedAccelVec):
        return int
    elif command in (StreamableCommands.GetRawGyroRate, StreamableCommands.GetCorrectedGyroRate, StreamableCommands.GetNormalizedGyroRate):
        return int
    elif command in (StreamableCommands.GetRawMagVec, StreamableCommands.GetCorrectedMagVec, StreamableCommands.GetNormalizedMagVec):
        return int
    return None

def get_valid_params(streamable_command: StreamableCommands, sensor: ThreespaceDevice):
    if streamable_command in (StreamableCommands.GetBarometerAltitudeById, StreamableCommands.GetBarometerPressureById):
        return sensor.get_available_baros()
    elif streamable_command in (StreamableCommands.GetRawAccelVec, StreamableCommands.GetCorrectedAccelVec, StreamableCommands.GetNormalizedAccelVec):
        return sensor.get_available_accels()
    elif streamable_command in (StreamableCommands.GetRawGyroRate, StreamableCommands.GetCorrectedGyroRate, StreamableCommands.GetNormalizedGyroRate):
        return sensor.get_available_gyros()
    elif streamable_command in (StreamableCommands.GetRawMagVec, StreamableCommands.GetCorrectedMagVec, StreamableCommands.GetNormalizedMagVec):
        return sensor.get_available_mags()
    return None

def build_all_data_chart_axis_options(streamable_commands: list[StreamableCommands], sensor: ThreespaceDevice):
    options: dict[StreamableCommands,DataChartAxisOption] = {}
    for cmd_enum in streamable_commands:
        cmd = threespaceCommandGetInfo(cmd_enum.value)
        display_name = ' '.join(re.findall(r'[A-Z][a-z]*', cmd_enum.name)[1:])
        option = DataChartAxisOption(display_name, cmd_enum=cmd_enum, cmd=cmd)
        option.valid_params = get_valid_params(cmd_enum, sensor)
        options[cmd_enum] = option
    return options

__bounds_dict = {
    StreamableCommands.GetTaredOrientation : (-1, 1),
    StreamableCommands.GetTaredOrientationAsEuler : (-3.14, 3.14),
    StreamableCommands.GetTaredOrientationAsMatrix : (-1, 1),
    StreamableCommands.GetTaredOrientationAsAxisAngle : (-6.28, 6.28),
    StreamableCommands.GetTaredOrientationAsTwoVector : (-1, 1),
    StreamableCommands.GetDifferenceQuaternion : (0, 1),
    StreamableCommands.GetUntaredOrientation : (-1, 1),
    StreamableCommands.GetUntaredOrientationAsEuler : (-3.14, 3.14),
    StreamableCommands.GetUntaredOrientationAsMatrix : (-1, 1),
    StreamableCommands.GetUntaredOrientationAsAxisAngle : (-6.28, 6.28),
    StreamableCommands.GetUntaredOrientationAsTwoVector : (-1, 1),
    StreamableCommands.GetTaredOrientationAsTwoVectorSensorFrame : (-1, 1),
    StreamableCommands.GetUntaredOrientationAsTwoVectorSensorFrame : (-1, 1),
    StreamableCommands.GetPrimaryBarometerPressure : (None, None),
    StreamableCommands.GetPrimaryBarometerAltitude : (None, None),
    StreamableCommands.GetBarometerAltitudeById : (None, None),
    StreamableCommands.GetBarometerPressureById : (None, None),
    StreamableCommands.GetAllPrimaryNormalizedData : (-1, 1),
    StreamableCommands.GetPrimaryNormalizedGyroRate : (-1, 1),
    StreamableCommands.GetPrimaryNormalizedAccelVec : (-1, 1),
    StreamableCommands.GetPrimaryNormalizedMagVec : (-1, 1),
    StreamableCommands.GetAllPrimaryCorrectedData : (-5, 5),
    StreamableCommands.GetPrimaryCorrectedGyroRate : (-5, 5),
    StreamableCommands.GetPrimaryCorrectedAccelVec : (-2, 2),
    StreamableCommands.GetPrimaryCorrectedMagVec : (-0.8, 0.8),
    StreamableCommands.GetPrimaryGlobalLinearAccel : (-2, 2),
    StreamableCommands.GetPrimaryLocalLinearAccel : (-2, 2),
    StreamableCommands.GetTemperatureCelsius : (None, None),
    StreamableCommands.GetTemperatureFahrenheit : (None, None),
    StreamableCommands.GetMotionlessConfidenceFactor : (0, 1),
    StreamableCommands.GetNormalizedGyroRate : (-1, 1),
    StreamableCommands.GetNormalizedAccelVec : (-1, 1),
    StreamableCommands.GetNormalizedMagVec : (-1, 1),
    StreamableCommands.GetCorrectedGyroRate : (-5, 5),
    StreamableCommands.GetCorrectedAccelVec : (-2, 2),
    StreamableCommands.GetCorrectedMagVec : (-0.8, 0.8),
    StreamableCommands.GetRawGyroRate : (-5, 5),
    StreamableCommands.GetRawAccelVec : (-2, 2),
    StreamableCommands.GetRawMagVec : (-0.8, 0.8),
    StreamableCommands.GetEeptsOldestStep : (None, None),
    StreamableCommands.GetEeptsNewestStep : (None, None),
    StreamableCommands.GetEeptsNumStepsAvailable : (None, None),
    StreamableCommands.GetTimestamp : (None, None),
    StreamableCommands.GetBatteryVoltage : (3, 5),
    StreamableCommands.GetBatteryPercent : (0, 100),
    StreamableCommands.GetBatteryStatus : (0, 3),
    StreamableCommands.GetGpsCoord : (None, None),
    StreamableCommands.GetGpsAltitude : (None, None),
    StreamableCommands.GetGpsFixState : (0, 6),
    StreamableCommands.GetGpsHdop : (0, 2),
    StreamableCommands.GetGpsSattelites : (0, 8),
    StreamableCommands.GetButtonState : (0, 1),
}

def modify_options(options: dict[StreamableCommands,DataChartAxisOption]):
    for cmd, axis in options.items():
        axis.bounds_y = __bounds_dict[cmd]
    

if __name__ == "__main__":
    from yostlabs.tss3.api import ThreespaceSensor
    sensor = ThreespaceSensor()
    port = sensor.ser.port
    sensor.cleanup()
    device = ThreespaceDevice(port)
    options = get_all_data_chart_axis_options(device)

    for option in options.values():
        print(option)

    new_options = {"None": None}
    new_options.update(options)

    #print(new_options)
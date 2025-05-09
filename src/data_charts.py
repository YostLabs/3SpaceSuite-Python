"""
Includes utility for working with data charts and configuration information
for how some data will show up
"""
from dataclasses import dataclass, field
from devices import ThreespaceDevice, StreamableCommands, threespaceCommandGetInfo, ThreespaceCommandInfo, ThreespaceStreamingOption
import re

@dataclass
class StreamOption:
    display_name: str

    cmd: StreamableCommands = None
    info: ThreespaceCommandInfo = None

    param_type: type = None
    valid_params: list = None


#--------------------------Retrieving options in various ways------------------------------------
def get_option(streamable_command: StreamableCommands):
    cmd = threespaceCommandGetInfo(streamable_command.value)
    display_name = ' '.join(re.findall(r'[A-Z][a-z]*', streamable_command.name)[1:])
    return StreamOption(display_name, streamable_command, cmd, get_param_type(streamable_command))

def get_options_from_list(streamable_commands: list[StreamableCommands]):
    return [get_option(v) for v in streamable_commands]

def get_all_options():
    return get_options_from_list(list(StreamableCommands))

def get_all_options_from_device(sensor: ThreespaceDevice):
    streamable_commands = sensor.get_streamable_commands()
    options = get_options_from_list(streamable_commands)
    for option in options: #Load valid params from the sensor
        option.valid_params = get_valid_params(option.cmd, sensor)
    return options

def get_options_from_slots(slots: list[ThreespaceStreamingOption]):
    #Creates an option list and also loads valid params based on the options supplied
    options: dict[StreamableCommands, StreamOption] = { }
    for slot in slots:
        if slot.cmd in options: #Already present, only handle updating the valid params
            if slot.param is not None:
                if options[slot.cmd].valid_params is None:
                    options[slot.cmd].valid_params = []
                options[slot.cmd].valid_params.append(slot.param)
            continue

        #Create the option and add it to the dict
        option = get_option(slot.cmd)
        if slot.param is not None:
            option.valid_params = [slot.param]
        options[slot.cmd] = option
    
    return list(options.values())

#-------------------------------METADATA HELPERS-----------------------------------------

__param_type_dict = {
    StreamableCommands.GetBarometerAltitudeById: int,
    StreamableCommands.GetBarometerPressureById: int,
    StreamableCommands.GetRawAccelVec: int,
    StreamableCommands.GetCorrectedAccelVec: int,
    StreamableCommands.GetNormalizedAccelVec: int,
    StreamableCommands.GetRawGyroRate: int,
    StreamableCommands.GetCorrectedGyroRate: int,
    StreamableCommands.GetNormalizedGyroRate: int,
    StreamableCommands.GetRawMagVec: int,
    StreamableCommands.GetCorrectedMagVec: int,
    StreamableCommands.GetNormalizedMagVec: int,
}

def get_param_type(streamable_command: StreamableCommands):
    if streamable_command in __param_type_dict: return __param_type_dict[streamable_command]
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

#--------------------------------------------------Config information specific to data charts-------------------------------------------

#The minimum upper and lower bounds to show on a graph
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

def get_min_bounds_for_command(cmd: StreamableCommands):
    return __bounds_dict.get(cmd, (None, None))

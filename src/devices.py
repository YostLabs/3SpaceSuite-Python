"""
Contains the publicly available device API
for each type of device that can be connected.
Also has some abstract devices, such as LoggerDevice
"""

#from Threespace.USB_ExampleClass import UsbCom
#from Threespace.ThreeSpaceAPI import ThreeSpaceSensor, Streamable, STREAM_CONTINUOUSLY
from yostlabs.tss3.api import ThreespaceSensor, ThreespaceComClass, ThreespaceSerialComClass, StreamableCommands, ThreespaceCommandInfo, threespaceCommandGetInfo, ThreespaceCmdResult
from yostlabs.communication.ble import ThreespaceBLEComClass
from yostlabs.tss3.utils.streaming import ThreespaceStreamingManager, ThreespaceStreamingOption, ThreespaceStreamingStatus
from yostlabs.tss3.utils.version import ThreespaceFirmwareUploader
import yostlabs.math.quaternion as yl_quat
import yostlabs.math.vector as yl_vec
from utility import Logger, Callback
import yostlabs.tss3.consts as threespace_consts

import platform
from typing import Callable, Any

import time

import traceback

class ThreespaceDevice:
    """
    All threespace sensor interaction is done through this class.
    The ThreeSpaceSensor (api) should NEVER be accessed anywhere
    else, only in this file.
    """
    
    FILTER_MODE_IMU: int = 0
    FILTER_MODE_QGRAD3: int = 1
    FILTER_MODE_KALMAN: int = 2

    DEFAULT_BIAS = [0, 0, 0]
    DEFAULT_MATRIX = [1, 0, 0, 0, 1, 0, 0, 0, 1]

    def __init__(self, com: ThreespaceComClass):
        self.com = com
        if isinstance(com, ThreespaceSerialComClass):
            com: ThreespaceSerialComClass
            self._name = "3Space" + str(self.com.ser.port)
        elif isinstance(com, ThreespaceBLEComClass):
            com: ThreespaceBLEComClass
            self._name = self.com.name
        else:
            self._name = "3SpaceUnknown"
        
        if self._name is None:
            self._name = "Unknown"
        
        self.property_update_callbacks = []

        self.silence_errors = False
        self.ignore_errors = False
        self.__ignore_errors = False #For internal purposes only, such as preventing error recursion
        self.error = ""
        self.on_error = Callback()

        self.on_disconnect = Callback()

        self.stream_mode = None
        self.stream_owner = None
        self.stream_stolen_callback = None

        self.disconnected = False
        self.metadata = None

        #Don't be opened by default
        self.__api = None
        self.streaming_manager: ThreespaceStreamingManager = None

        #These will be loaded when initially opened
        #self.dirty = False
        self.cached_serial_number = None
        self.cached_axis_info = None

    @property
    def is_open(self):
        return self.__api is not None

    @property
    def in_bootloader(self):
        return self.__api.in_bootloader
    
    @property
    def com_type(self):
        if isinstance(self.com, ThreespaceSerialComClass):
            return "Serial"
        elif isinstance(self.com, ThreespaceBLEComClass):
            return "BLE"
        else:
            return "UNKNOWN"

    def open(self):
        if self.is_open: return
        self.com.open()
        try:
            refresh_timeout = None
            if isinstance(self.com, ThreespaceBLEComClass):
                refresh_timeout = 0.1 #To help with connecting to a BLE sensor when it was initially streaming
            self.__api = ThreespaceSensor(self.com, verbose=True, initial_clear_timeout=refresh_timeout)
        #Don't allow the com to get stuck open
        except Exception as e:
            self.com.close()
            raise e
        if self.__api.in_bootloader: 
            return
        self.streaming_manager = ThreespaceStreamingManager(self.__api)
        self.streaming_manager.enable()
        self.cached_serial_number = self.get_serial_number()
        self.cache_axis_order()

    def close(self):
        if not self.is_open: return
        try:
            self.__api.cleanup()
        except Exception as e:
            self.report_error(e)
        self.__api = None

    def disconnect(self):
        self.on_disconnect._notify(self)
        #Notify is called first in case any subscribers want to do some cleanup
        self.close()

    @property
    def com_port(self):
        if isinstance(self.com, ThreespaceSerialComClass):
            return self.com.ser.port
        return ""

    def update(self):
        if not self.is_open: return

        if self.streaming_manager is None: return
        try:
            self.streaming_manager.update()
        except Exception as e:
            self.report_error(e)

    def report_error(self, error: Exception):
        if self.ignore_errors or self.__ignore_errors:
            return
        if not self.silence_errors:
            Logger.log_error(f"{type(error).__name__}: {str(error)}")
            #Useful for debugging. But also not necessary for every error
            #EX: User really doesn't need to see this when an error occurs from an expected action, such as unplugging the sensor
            #but it is useful when an unexpected error occurs
            traceback.print_exc()
        self.__ignore_errors = True #Ignore errors generated while processing errors
        self.on_error._notify(self, f"{type(error).__name__}: {str(error)}")
        self.__ignore_errors = False

    def pause_streaming(self, lock: object):
        return self.streaming_manager.pause(lock)

    def resume_streaming(self, lock: object):
        return self.streaming_manager.resume(lock)

    def register_streaming_callback(self, callback: Callable[[ThreespaceStreamingStatus,Any],None], hz=None, only_newest=False, user_data=None):
        self.streaming_manager.register_callback(callback, hz=hz, only_newest=only_newest, user_data=user_data)
    
    def unregister_streaming_callback(self, callback: Callback):
        return self.streaming_manager.unregister_callback(callback)
        
    def register_streaming_command(self, owner: object, command: StreamableCommands|ThreespaceStreamingOption, param=None, immediate_update=True):
        return self.streaming_manager.register_command(owner, command, param=param, immediate_update=immediate_update)
    
    def unregister_streaming_command(self, owner: object, command: StreamableCommands|ThreespaceStreamingOption, param=None, immediate_update=True):
        return self.streaming_manager.unregister_command(owner, command, param=param, immediate_update=immediate_update)
    
    def unregister_all_streaming_commands_from_owner(self, owner: object, immediate_update: bool = True):
        return self.streaming_manager.unregister_all_commands_from_owner(owner, immediate_update=immediate_update)

    def update_streaming_settings(self):
        return self.streaming_manager.apply_updated_settings()

    def get_streaming_value(self, command: StreamableCommands|ThreespaceStreamingOption, param=None):
        return self.streaming_manager.get_value(command, param=param)
    
    def get_streaming_last_response(self):
        return self.streaming_manager.get_last_response()

    def get_streaming_labels(self):
        return self.streaming_manager.get_response_labels()

    def force_reset_streaming(self) -> bool:
        return self.streaming_manager.reset()

    def lock_streaming_modifications(self, owner: object) -> bool:
        return self.streaming_manager.lock_modifications(owner)

    def unlock_streaming_modifications(self, owner: object) -> bool:
        return self.streaming_manager.unlock_modifications(owner)

    def is_api_streaming(self):
        if not self.is_open: return False
        return self.__api.is_streaming is True

    def get_streaming_batch(self):
        return self.__api.getStreamingBatch()

    def reset_timestamp(self):
        self.__api.set_settings(timestamp=0)
        return True
    
    def set_timestamp(self, time):
        self.__api.set_settings(timestmap=time)

    def set_response_header(self, success_fail=False, timestamp=False, echo=False, checksum=False, id=False, serial_number=False, data_len=False):        
        return self.__api.set_settings(header_status=success_fail, header_timestamp=timestamp, 
                                       header_echo=echo, header_checksum=checksum, 
                                       header_serial=serial_number, header_length=data_len)

    def get_cached_header(self):
        return self.__api.header_info.bitfield

    def get_metadata_dict(self):
        return self.metadata
    
    def set_metadata(self, key, value):
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value

    def get_all_settings(self) -> dict[str,str]:
        return self.__api.get_settings("settings")

    def start_eepts(self):
        self.__api.eeptsStart()

    def stop_eepts(self):
        self.__api.eeptsStop()
    
    def eepts_reset_settings(self):
        self.__api.set_settings("pts_default")

    def eepts_set_static_offset(self):
        self.__api.eeptsAutoOffset()
        #When using the auto offset, the declination will be naturally included into the offset
        self.__api.set_settings(pts_auto_declination=0, pts_mag_declination=0)

    def set_settings(self, **kwargs):
        self.__api.set_settings(**kwargs)

    def restore_factory_settings(self):
        self.__api.set_settings("default")

    def commit_settings(self):
        self.__api.commitSettings()

    def restart_sensor(self):
        self.streaming_manager.reset() #Disable anything relying on streaming since sensor must reset
        self.__api.softwareReset()
        self.cache_axis_order()

    def set_led_color(self, rgb: list[int, int, int]):
        self.__api.set_settings(led_rgb=f"{rgb[0]/255},{rgb[1]/255},{rgb[2]/255}")

    def get_raw_mag(self, id: int):
        return self.__api.getRawMagVec(id).data
    
    def get_raw_accel(self, id: int):
        return self.__api.getRawAccelVec(id).data    
    
    def get_streamable_commands(self) -> list[StreamableCommands]: #TO DO - Make this work
        commands = self.__api.get_settings("streamable_commands")
        registered_commands = []
        for v in commands.split(','):
            try:
                registered_commands.append(StreamableCommands(int(v)))
            except:
                Logger.log_warning(f"Sensor {self.name} has an unregistered streaming command {v}")
        return registered_commands
    
    def get_available_mags(self):
        return self.__api.valid_mags.copy()
    
    def get_available_mags_str(self):
        components = self.get_available_components()
        return [v for v in components if "Mag" in v]    
    
    def get_available_accels(self):
        return self.__api.valid_accels.copy()

    def get_available_accels_str(self):
        components = self.get_available_components()
        return [v for v in components if "Accel" in v]
    
    def get_available_gyros(self):
        return self.__api.valid_gyros.copy()
    
    def get_available_gyros_str(self):
        components = self.get_available_components()
        return [v for v in components if "Gyro" in v]

    def get_available_baros(self):
        return self.__api.valid_baros.copy()
    
    def get_available_baros_str(self):
        components = self.get_available_components()
        return [v for v in components if "Baro" in v]    
    
    def get_available_components(self):
        components = self.__api.get_settings("valid_components")
        components = components.split(',')
        return components
    
    def get_odrs(self, type: str, *ids):
        prefix = f"odr_{type}"
        result = self.__api.get_settings(';'.join(f"{prefix}{v}" for v in ids), format="Dict")
        return {int(k.removeprefix(prefix)) : int(v) for k, v in result.items()}

    def get_accel_odrs(self, *ids):
        return self.get_odrs("accel", *ids)

    def get_mag_odrs(self, *ids):
        return self.get_odrs("mag", *ids)    
    
    def set_odrs(self, type: str, odrs: dict[int, int]):
        prefix = f"odr_{type}"
        odrs = {f"{prefix}{k}" : v for k, v in odrs.items()}
        self.__api.set_settings(**odrs)

    def set_accel_odrs(self, odrs: dict[int, int]):
        self.set_odrs("accel", odrs)
    
    def set_mag_odrs(self, odrs: dict[int, int]):
        self.set_odrs("mag", odrs)

    def get_axis_order(self) -> str:
        return self.__api.get_settings("axis_order")

    def set_axis_order(self, order: str):
        result = self.__api.set_settings(axis_order=order)
        if result[0] == 0: 
            self.cache_axis_order(order)
        return result

    def cache_axis_order(self, axis_str: str = None):
        if axis_str is None:
            axis_str = self.get_axis_order()
        self.cached_axis_info = yl_vec.parse_axis_string_info(axis_str)
    
    @staticmethod
    def get_axis_info(order):
        return 

    def get_gyro_calibration(self, id: int):
        return self.__get_calibration(f"gyro{id}")

    def get_mag_calibration(self, id: int):
        return self.__get_calibration(f"mag{id}")

    def get_accel_calibration(self, id: int):
        """Returns the matrix followed by the bias"""
        return self.__get_calibration(f"accel{id}")
    
    def set_gyro_calibration(self, id: int, mat: list[float] = None, bias: list[float] = None):
        self.__set_calibration(f"gyro{id}", mat=mat, bias=bias)

    def set_mag_calibration(self, id: int, mat: list[float] = None, bias: list[float] = None):
        self.__set_calibration(f"mag{id}", mat=mat, bias=bias)

    def set_accel_calibration(self, id: int, mat: list[float] = None, bias: list[float] = None):
        self.__set_calibration(f"accel{id}", mat=mat, bias=bias)

    def __set_calibration(self, id_key: str, mat: list[float] = None, bias: list[float] = None):
        if mat is None and bias is None: return
        set_params = {}
        if mat is not None:
            set_params[f"calib_mat_{id_key}"] = mat
        if bias is not None:
            set_params[f"calib_bias_{id_key}"] = bias
        self.__api.set_settings(**set_params)

    def __get_calibration(self, id_key: str):
        mat_key = f"calib_mat_{id_key}"
        bias_key = f"calib_bias_{id_key}"
        calib = self.__api.get_settings(f"{mat_key};{bias_key}")
        return [float(v) for v in calib[mat_key].split(',')], [float(v) for v in calib[bias_key].split(',')]

    def get_detected_components(self):
        return self.__api.get_settings("valid_components")

    def get_serial_number(self):
        if self.__api.in_bootloader:
            return self.__api.bootloader_get_sn()
        else:
            return int(self.__api.get_settings("serial_number"), 16)

    def get_firmware_version(self):
        return self.__api.get_settings("version_firmware")

    def get_hardware_version(self):
        return self.__api.get_settings("version_hardware")

    def get_filter_mode(self):
        filter_dict = {
            0: "IMU",
            1: "Q-GRAD3",
            2: "Kalman"
        }
        r = int(self.__api.get_settings("filter_mode"))
        return filter_dict.get(r, f"Unknown: {r}")
    
    def set_filter_mode(self, mode: int):
        self.__api.set_settings(filter_mode=mode)

    def set_accel_enabled(self, enabled: bool):
        self.__api.set_settings(accel_enabled=int(enabled))

    def set_mag_enabled(self, enabled: bool):
        self.__api.set_settings(mag_enabled=int(enabled))

    def set_gyro_enabled(self, enabled: bool):
        self.__api.set_settings(gyro_enabled=int(enabled))        

    def is_accel_enabled(self):
        return bool(int(self.__api.get_settings("accel_enabled")))
    
    def is_gyro_enabled(self):
        return bool(int(self.__api.get_settings("gyro_enabled")))
    
    def is_mag_enabled(self):
        return bool(int(self.__api.get_settings("mag_enabled")))

    def set_cached_settings_dirty(self):
        #self.dirty = True
        self.__api.set_cached_settings_dirty()

    def send_ascii_command(self, ascii):
        if self.is_api_streaming():
            return False
        command = f'{ascii}\n'.encode()
        self.__api.com.write(command)
        self.set_cached_settings_dirty() #May have modified settings, make sure it updates properly next time
        return True
    
    def send_raw_data(self, data: bytes):
        self.__api.com.write(data)
        print("Wrote:", data)
        self.set_cached_settings_dirty()

    def read_com_port(self, decode=True):
        """
        Attempts to read any values in the com port.
        This function may return None in situations where
        another part of the program has access to the com port
        """
        if self.is_api_streaming():
            return ''
        
        try:
            data = self.__api.com.read_all()
        except Exception as e:
            #For now, leaving out the reconnect as it can cause problems
            #Specifically, if done while in terminal, when entering bootloader, will automatically reconnect
            #to the renumerated port. Then entering the orientation window could cause it to send bootloader commands
            #that corrupt the firmware. Would rather it just instantly disconnects.
            self.report_error(e)
            return ''            
            start_time = time.time()
            error = None

            #The reconnect will not work without giving the sensor time to actually finish restarting.
            while time.time() - start_time < 1:
                try:
                    self.__api.check_dirty() #May have been a reboot. This should reconnect
                except Exception as e:
                    error = e
                else: #Successfully reconnected
                    error = None
                    break

            #Failed to reconnect
            if error is not None:
                self.report_error(error)
                return ''
            
            #Reconnected, try a read
            try:
                data = self.__api.com.read_all() #check_dirty didn't work, so actually error
            except Exception as e:
                self.report_error(e)
                return ''
             
        if not decode:
            return data

        try:
            decoded = data.decode()
            return decoded #Whatever data just wasn't ascii
        except Exception:
            return data

    def is_connected(self, prevent_disconnect=False):
        if self.is_api_streaming():
            return True
        try:
            if prevent_disconnect:
                self.ignore_errors = True
            self.get_serial_number()
            if prevent_disconnect:
                self.ignore_errors = False
            return True
        except:
            return False
        # if platform.system() == 'Linux':
        #     if self.is_api_streaming():
        #         return True
        #     try:
        #         version = self.__api.getFirmwareVersionString()
        #         if len(version) == 0:
        #             return False
        #         return True
        #     except Exception:
        #         return False
        # else:
        #     try:
        #         self.com.sensor.in_waiting #Fails if not connected
        #         return True
        #     except:
        #         return False

    def base_tare_with_current_orientation(self):
        self.__api.setBaseTareWithCurrentOrientation()

    def set_base_tare(self, quat: list[float]):
        self.__api.set_settings(base_tare=','.join(str(v) for v in quat))
    
    def tare_with_current_orientation(self):
        self.__api.tareWithCurrentOrientation()
    
    def set_tare(self, quat: list[float]):
        self.__api.set_settings(tare_quat=','.join(str(v) for v in quat))

    def base_offset_with_current_orientation(self):
        self.__api.setBaseOffsetWithCurrentOrientation()
    
    def set_base_offset(self, quat: list[float]):
        self.__api.set_settings(base_offset=','.join(str(v) for v in quat))

    def offset_with_current_orientation(self):
        self.__api.setOffsetWithCurrentOrientation()

    def convert_quat_order(self, quat: list[float], new_order: str):
        return yl_quat.quaternion_swap_axes_fast(quat, self.cached_axis_info, yl_vec.parse_axis_string_info(new_order))
    
    def convert_quat_order_fast(self, quat: list[float], new_order_info: list[list, list, bool]):
        return yl_quat.quaternion_swap_axes_fast(quat, self.cached_axis_info, new_order_info)

    def is_right_handed(self):
        return self.cached_axis_info[2]

    def set_offset(self, quat: list[float]):
        self.__api.set_settings(offset=','.join(str(v) for v in quat))

    def start_gyro_autocalibration(self):
        self.__api.beginPassiveAutoCalibration(threespace_consts.PASSIVE_CALIBRATE_GYRO)

    def upload_firmware(self, path: str):
        uploader = ThreespaceFirmwareUploader(self.__api, path)
        uploader.upload_firmware()
    
    def get_firmware_uploader(self):
        return ThreespaceFirmwareUploader(self.__api)

    def boot_firmware(self):
        if not self.__api.in_bootloader: return
        print("Bootloader booting firmware.")
        print(self.__api.com)
        self.__api.bootloader_boot_firmware()

    def is_firmware_valid(self):
        if self.__api.in_bootloader:
            return bool(self.__api.bootloader_get_state() & threespace_consts.FIRMWARE_VALID_BIT)
        else:
            return True #Already in firmware, so must be valid

    def cleanup(self):
        try:
            if self.__api is not None:
                self.__api.cleanup()
                #self.force_reset_streaming()
        except Exception as e: 
            print("Failed to cleanup", self.name)
            print(e)
            pass

    def __notify_property_update(self):
        for callback in self.property_update_callbacks:
            callback(self)

    def subscribe_property_update(self, callback):
        self.property_update_callbacks.append(callback)
    
    def unsubscribe_property_update(self, callback):
        self.property_update_callbacks.remove(callback)

    @property
    def name(self):
        return self._name
    
    def type(self):
        return self._type

    @name.setter
    def name(self, name):
        self._name = name
        self.__notify_property_update()

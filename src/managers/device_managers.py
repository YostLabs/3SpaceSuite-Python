"""
Handles managing the connected devices as 
well as connecting the devices to the visual
elements that require access to them
"""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from managers.settings_manager import SettingsManager

from dpg_ext.global_lock import dpg_lock

from devices import ThreespaceDevice
from typing import NamedTuple
from gui.sensor_windows import SensorBanner, SensorMasterWindow
from gui.core_ui import BannerMenu, DynamicViewport
from managers.macro_manager import MacroManager

from yostlabs.tss3.api import ThreespaceSensor

#Import the communication objects used
from yostlabs.communication.ble import ThreespaceComClass
from yostlabs.communication.serial import ThreespaceSerialComClass
from yostlabs.communication.ble import ThreespaceBLEComClass

import serial
import serial.tools.list_ports

import platform

from utility import Logger, Callback
import time

import dataclasses

def is_threespace_detected(port):
    try:
        sensor = ThreespaceSensor(port, timeout=0.05)
    except:
        return False
    else:
        sensor.cleanup()
        return True

class DeviceManager:

    def __init__(self, banner_menu: BannerMenu, window_viewport: DynamicViewport, settings_manager: SettingsManager):
        """
        banner_menu: menu for putting the device banner to select
        window_viewport: The parent object for where to place device windows
        """
        self.threespace_manager = ThreespaceManager(banner_menu, window_viewport, settings_manager)

    def update(self):
        self.threespace_manager.update()

    def discover_devices(self):
        Logger.log_info("Discovering Devices")
        self.threespace_manager.discover_devices()

    def cleanup(self):
        self.threespace_manager.cleanup()
    
    def update(self):
        self.threespace_manager.update()

ThreespaceGroup = NamedTuple("ThreespaceGroup", [("device", ThreespaceDevice), ("banner", SensorBanner), ("main_window", SensorMasterWindow)])

@dataclasses.dataclass
class SerialSettings:
    enabled: bool = True

@dataclasses.dataclass
class BleSettings:
    enabled: bool = True
    filter: str = "YL-TSS-"
    show_hidden: bool = False
    allow: list[str] = dataclasses.field(default_factory=list)
    deny: list[str] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class ThreespaceManagerSettings:
    serial: SerialSettings = dataclasses.field(default_factory=SerialSettings)
    ble: BleSettings = dataclasses.field(default_factory=BleSettings)

    def __post_init__(self):
        if isinstance(self.serial, dict):
            self.serial = SerialSettings(**self.serial)
        if isinstance(self.ble, dict):
            self.ble = BleSettings(**self.ble)

class ThreespaceManager:

    POTENTIAL_RPI_PORTS = ["/dev/ttyAMA0", "/dev/ttyAMA1", "/dev/ttyAMA2", "/dev/ttyAMA3", "/dev/ttyAMA4", "/dev/ttyAMA5"]

    def __init__(self, banner_menu: BannerMenu, window_viewport: DynamicViewport, settings_manager: SettingsManager):
        self.devices: dict[ThreespaceComClass, ThreespaceGroup] = {}
        self.banner_menu = banner_menu
        self.window_viewport = window_viewport

        self.settings_manager = settings_manager
        self.macro_manager = MacroManager(settings_manager)

        self.periodic_update_rate = 0.5
        self.last_update_time = time.time()

        self.map_fname = "device_map.json"
        self.device_mapping = {}
        self.load_device_names()

        #This is used to delay error handling for when it is safe to do so
        self.queued_for_removal = []

        self.on_device_opened = Callback()

        self.load_settings()

        self.ble_supported = False
        try:
            ThreespaceBLEComClass.set_scanner_continous(True)
            self.ble_supported = True
        except Exception as e:
            Logger.log_error(f"Failed to start BLE scanning: {e}")

    def notify_opened(self, device: ThreespaceDevice):
        self.on_device_opened._notify(device)

    def save_settings(self):
        if self.settings is None: return
        self.settings_manager.save("tss_device_manager.json", self.settings, default=lambda o: dataclasses.asdict(o))

    def load_settings(self):
        setting_dict = self.settings_manager.load("tss_device_manager.json")
        if setting_dict is None:
            self.settings = ThreespaceManagerSettings()
        else:
            self.settings = ThreespaceManagerSettings(**setting_dict)

    def __show_ble_device(self, device: ThreespaceBLEComClass):
        if device.address in self.settings.ble.deny: return False #In the reject List
        if self.settings.ble.show_hidden: return True #Show all is set
        if device.address in self.settings.ble.allow: return True #explicitly allowed
        if device.name is None: return False #None names have no chance of matching the filter
        if device.name.startswith(self.settings.ble.filter): return True #Matched the filter, so allowed
        return False #Default to hidden unless allowed by the settings above
    
    #---------------------Find potential com classes for ThreespaceSensors--------------------------------
    def __discover_coms(self):
        valid_coms = []
        if self.settings.serial.enabled:
            for port in ThreespaceSerialComClass.enumerate_ports():
                if port.pid & ThreespaceSerialComClass.PID_V3_MASK == ThreespaceSerialComClass.PID_V3_MASK or port.pid == ThreespaceSerialComClass.PID_BOOTLOADER:
                    ser = serial.Serial(None, baudrate=115200, timeout=2) #By seperating the port assignment from the constructor, can create the object without automatically opening the port
                    ser.port = port.device
                    valid_coms.append(ThreespaceSerialComClass(ser))
        
        if self.ble_supported and self.settings.ble.enabled:
            for ble_device in ThreespaceBLEComClass.auto_detect():
                if not self.__show_ble_device(ble_device): continue
                valid_coms.append(ble_device)
        
        return valid_coms

    #-----------------------------Update/Remove connected ports based on potential ports--------------------------------
    def __update_registered_devices(self, available_coms: list[ThreespaceComClass]):
        #Cache this before adding coms to minimize checks
        cur_devices = list(self.devices.keys())

        #Add ports that haven't been registered
        for com in available_coms:
            if not self.is_com_registered(com):
                self.add_device_by_com(com)
            else:
                self.update_device_by_com(com)

        for com in cur_devices:
            #--------------Handle active devices----------------------
            if self.devices[com].device.is_open:
                #If its a ble device, make sure to flag its address as a valid address
                if isinstance(com, ThreespaceBLEComClass) and not com.address in self.settings.ble.allow:
                    self.settings.ble.allow.append(com.address)
            
            #-------------Handle inactive devices------------------
            else:
                available = False
                for available_com in available_coms:
                    if self.are_coms_equal(com, available_com): #The current device is still available for connection, so leave it connected
                        available = True
                        break
                if not available:
                    self.remove_device_by_com(com)

    def discover_devices(self):
        self.__update_registered_devices(self.__discover_coms())

    def are_coms_equal(self, a: ThreespaceComClass, b: ThreespaceComClass):
        if type(a) is not type(b): return False
        if isinstance(a, ThreespaceSerialComClass):
            return a.ser.port == b.ser.port
        elif isinstance(a, ThreespaceBLEComClass):
            return a.client.address == b.client.address
        return False

    #Com classes are not required to implement == or hash, so this is required to use coms
    def is_com_registered(self, com: ThreespaceComClass):
        return self.get_registered_com(com) is not None
    
    def get_registered_com(self, com: ThreespaceComClass):
        """Converts from a newly created com to the one used in the dictionary"""
        for other in self.devices:
            if self.are_coms_equal(com, other):
                return other
        return None

    def add_device_by_com(self, com: ThreespaceComClass):
        device = ThreespaceDevice(com)
        # if com.name in self.device_mapping:
        #     device.name = self.device_mapping[com.name]
        default_name = com.name
        if default_name.lower() in (f"com{i}" for i in range(10)):
            default_name = f"{default_name[:3]}0{default_name[3]}"
        device.name = default_name
        Logger.log_info(f"Detected: {com.name}")
        device.on_error.subscribe(self.__on_sensor_error)
        device.on_disconnect.subscribe(self.__on_sensor_disconnect)
        with dpg_lock():
            banner = SensorBanner(device)
            group = ThreespaceGroup(device, banner, SensorMasterWindow(device, banner, self.macro_manager, on_connect=self.notify_opened))
        self.devices[com] = group
        self.banner_menu.add_banner(group.banner)
        group.banner.add_selected_callback(lambda _: self.load_sensor_window(com))        

    def update_device_by_com(self, com: ThreespaceComClass):
        registered_com = self.get_registered_com(com)
        if registered_com is None: return
        if isinstance(registered_com, ThreespaceBLEComClass):
            if com.name is not None and com.name != registered_com.name: #Name was updated
                registered_com._ThresspaceBLEComClass__name = com.name
                self.devices[registered_com].device.name = com.name
        pass

    def remove_device_by_com(self, com: ThreespaceComClass):
        com = self.get_registered_com(com)
        if com is None: return
        group = self.devices.pop(com)
        group.main_window.delete()
        try:
            group.device.cleanup()
        except: pass
        self.banner_menu.remove_banner(group.banner, auto_select=True)
        Logger.log_warning("Disconnected:" + group.device.name)
    
    def __on_sensor_error(self, device: ThreespaceDevice, err: str):
        if not device.silence_errors: #This would get spammed while logging because the cleanup fails to stop the streaming thread when called due to the streaming thread throwing an exception
            print("Removing Device:", device.name)
            print("Reason:", err)
        
        #After disconnection, don't want spammed with other read errors
        device.silence_errors = True
        device.ignore_errors = True #Don't want recursive erroring
        self.queued_for_removal.append(device.com)
    
    def __on_sensor_disconnect(self, device: ThreespaceDevice):
        device.silence_errors = True
        device.ignore_errors = True
        self.queued_for_removal.append(device.com)

    def load_sensor_window(self, com):
        self.window_viewport.set_view(self.devices[com].main_window)

    def get_devices(self):
        return [v.device for v in self.devices.values()]

    def load_device_names(self):
        self.device_mapping = self.settings_manager.load(self.map_fname)
        if self.device_mapping is None:
            self.device_mapping = {}

    def save_device_names(self):
        """
        Maps the current device names for each com port into
        a file to save names between runs
        """
        for group in self.devices.values():
            port = group.device.com.name
            name = group.device.name
            self.device_mapping[port] = name
        
        self.settings_manager.save(self.map_fname, self.device_mapping)

    def cleanup(self):
        for group in self.devices.values():
            #First try and clean up each window. This allows windows to change back modified state.
            #This includes things like streaming settings, odr settings & axis settings (calibration), ...
            try:
                group.main_window.delete()
            except Exception as e:
                print("Failed to delete main window:", e)

            #Just in case the above failed to properly clean everything up
            try:
                if group.device.is_api_streaming():
                    group.device.force_reset_streaming()
            except Exception as e:
                print("Failed to cleanup streaming:", e)

            try:
                group.device.cleanup()
            except Exception as e:
                print("Failed to force cleanup device", e)

        self.save_device_names()
        self.save_settings()

    def update(self):
        """
        Determines if a device has become disconnected without the user
        having to send commands manually. Periodically called by GeneralManager
        in main loop
        """
        
        #Update all the sensors
        for group in self.devices.values():
            group.device.update()

        #Clear any sensors that need removed
        for com in self.queued_for_removal:
            com = self.get_registered_com(com)
            self.remove_device_by_com(com)
        self.queued_for_removal.clear()

        #Every so often, discover more devices
        if time.time() - self.last_update_time > self.periodic_update_rate:
            self.discover_devices()
            self.last_update_time = time.time()
            # to_disconnect = []
            # for group in self.devices.values():
            #     sensor = group.device
            #     if not sensor.is_connected(prevent_disconnect=True): #Will disconnect all at the end to avoid loop modifications while looping
            #         to_disconnect.append(group.device.port)
            # for port in to_disconnect:
            #     self.remove_device_by_port(port)

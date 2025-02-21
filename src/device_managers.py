"""
Handles managing the connected devices as 
well as connecting the devices to the visual
elements that require access to them
"""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from settings_manager import SettingsManager

from dpg_ext.global_lock import dpg_lock

from devices import ThreespaceDevice
from typing import NamedTuple
from sensor_windows import SensorBanner, SensorMasterWindow
from core_ui import BannerMenu, DynamicViewport
from macro_manager import MacroManager

from yostlabs.tss3.api import ThreespaceSensor, ThreespaceSerialComClass, ThreespaceComClass
from yostlabs.tss3.api import ThreespaceSensor, ThreespaceSerialComClass, ThreespaceComClass

import serial
import serial.tools.list_ports

import platform

from utility import Logger
import time

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

import dearpygui.dearpygui as dpg
ThreespaceGroup = NamedTuple("ThreespaceGroup", [("device", ThreespaceDevice), ("banner", SensorBanner), ("main_window", SensorMasterWindow)])
from macro_manager import MacroConfigurationWindow
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

    def discover_devices(self):
        #Find what ports have ThreeSpace Sensors
        valid_coms = []
        for port in ThreespaceSerialComClass.enumerate_ports():
            if port.pid & ThreespaceSerialComClass.PID_V3_MASK == ThreespaceSerialComClass.PID_V3_MASK or port.pid == ThreespaceSerialComClass.PID_BOOTLOADER:
                ser = serial.Serial(None, baudrate=115200, timeout=2) #By seperating the port assignment from the constructor, can create the object without automatically opening the port
                ser.port = port.device
                valid_coms.append(ThreespaceSerialComClass(ser))
        
        #Remove ports that have been disconnected
        cur_devices = list(self.devices.keys())
        for com in cur_devices:
            valid = False
            for other in valid_coms:
                if self.are_coms_equal(com, other):
                    valid = True
                    break
            if not valid:
                self.remove_device_by_com(com)

        #Add ports that haven't been connected
        for com in valid_coms:
            if not self.is_com_registered(com):
                self.add_device_by_com(com)

        # if platform.system() == 'Linux': #For Linux, gotta also browse the RPI UART Ports
        #     for port in self.POTENTIAL_RPI_PORTS:
        #         if port in self.devices:
        #             if not self.devices[port].device.is_connected(prevent_disconnect=True): #Prevent disconnect just meant to silence errors
        #                 self.remove_device_by_port(port)
        #         else:
        #             if is_threespace_detected(port):
        #                 self.add_device_by_port(port)
    
    def are_coms_equal(self, a: ThreespaceComClass, b: ThreespaceComClass):
        if type(a) is not type(b): return False
        if isinstance(a, ThreespaceSerialComClass):
            return a.ser.port == b.ser.port
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
        if com.name in self.device_mapping:
            device.name = self.device_mapping[com.name]
        Logger.log_info(f"Detected: {com.name}")
        device.on_error.subscribe(self.__on_sensor_error)
        device.on_disconnect.subscribe(self.__on_sensor_disconnect)
        with dpg_lock():
            banner = SensorBanner(device)
            group = ThreespaceGroup(device, banner, SensorMasterWindow(device, banner, self.macro_manager))
        self.devices[com] = group
        self.banner_menu.add_banner(group.banner)
        group.banner.add_selected_callback(lambda _: self.load_sensor_window(com))        

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
            except: pass

            #Just in case the above failed to properly clean everything up
            try:
                if group.device.is_api_streaming():
                        group.device.force_reset_streaming()
                group.device.cleanup()
            except: pass
        self.save_device_names()

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

from core_ui import BannerMenu, DynamicViewport
from logger_windows import LoggerBanner, DataLogWindow, LoggerMasterWindow

from device_managers import DeviceManager
from settings_manager import SettingsManager

from default_window import DefaultWindow

from log_data import DataLogger

class GeneralManager:

    def __init__(self, banner_menu: BannerMenu, window_viewport: DynamicViewport):
        self.viewport = window_viewport
        self.banner_menu = banner_menu

        self.settings_manager = SettingsManager()
        self.device_manager = DeviceManager(banner_menu, window_viewport, self.settings_manager)
        self.logger_manager = LoggerManager(banner_menu, window_viewport, self.device_manager)

        self.main_window = DefaultWindow()
    
    def load_main_window(self):
        self.banner_menu.set_banner(None)
        self.viewport.set_view(self.main_window)

    def cleanup(self):
        self.settings_manager.cleanup()
        self.device_manager.cleanup()
        self.logger_manager.cleanup()

class LoggerManager:

    def __init__(self, banner_menu: BannerMenu, window_viewport: DynamicViewport, 
                 device_manager: DeviceManager):

        self.banner_menu = banner_menu
        self.window_viewport = window_viewport
        self.banner = LoggerBanner(text="Data", on_select=self.__load_window)
        self.banner_menu.add_banner(self.banner)

        self.data_logger = DataLogger()
        self.logger_window = LoggerMasterWindow(device_manager, self.data_logger)
    
    def __load_window(self, button):
        self.window_viewport.set_view(self.logger_window)

    def cleanup(self):
        if self.data_logger.is_logging():
            self.data_logger.stop_logging()
        self.logger_window.delete()

    def update(self):
        if self.data_logger.is_logging():
            self.data_logger.update()
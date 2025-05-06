from gui.core_ui import BannerMenu, DynamicViewport
from gui.logger_windows import LoggerBanner, DataLogWindow, LoggerMasterWindow

from managers.device_managers import DeviceManager
from managers.settings_manager import SettingsManager, GenericSettingsManager
from managers.macro_manager import MacroManager

from gui.default_window import DefaultWindow

from data_log.log_data import DataLogger
from data_log.log_settings import LogSettings, LOG_SETTINGS_KEY

import version

class GeneralManager:

    def __init__(self, banner_menu: BannerMenu, window_viewport: DynamicViewport):
        self.viewport = window_viewport
        self.banner_menu = banner_menu

        self.settings_manager = SettingsManager()
        GenericSettingsManager.init(self.settings_manager)
        self.device_manager = DeviceManager(banner_menu, window_viewport, self.settings_manager)
        self.logger_manager = LoggerManager(banner_menu, window_viewport, self.device_manager)

        self.main_window = DefaultWindow()
        version.load_version()
    
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
        self.banner = LoggerBanner(text="Data", on_select=self.__load_window, height=50)
        self.banner_menu.add_banner(self.banner)

        log_settings_dict = GenericSettingsManager.get_local(LOG_SETTINGS_KEY, None)
        self.log_settings = LogSettings() if log_settings_dict is None else LogSettings.from_dict(log_settings_dict)
        self.data_logger = DataLogger()
        self.logger_window = LoggerMasterWindow(device_manager, self.data_logger, self.log_settings)
    
    def __load_window(self, button):
        self.window_viewport.set_view(self.logger_window)

    def cleanup(self):
        if self.data_logger.is_logging():
            self.data_logger.stop_logging()
        self.logger_window.delete()
        print("Saving log settings:", self.log_settings.to_dict())
        GenericSettingsManager.save_local(LOG_SETTINGS_KEY, self.log_settings.to_dict())


    def update(self):
        if self.data_logger.is_logging():
            self.data_logger.update()
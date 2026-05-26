import dearpygui.dearpygui as dpg
from gui.setting_gui.setting_structures import DpgSetting
from gui.setting_gui.setting_structures_custom import *
from yostlabs.tss3 import ThreespaceSensor
from gui.core_ui import DpgWizard, DpgWizardPageBasic

class LogDataSelectionPage(DpgWizardPageBasic):

    def __init__(self, descriptors: dict[str, ThreespaceSettingDescriptor], **kwargs):
        super().__init__(title="Data Selection", **kwargs)

        self.descriptors = descriptors
        self.header_enabled_setting = DpgSetting.create(descriptors["log_header_enabled"])
        self.header_enabled_setting.on_change.subscribe(self.__on_header_enabled_changed)
        self.header_settings = ["header_status", "header_timestamp", "header_echo", "header_checksum", "header_serial", "header_length"]

    def create_view(self):
        dpg.push_container_stack(super().create_view())
        self.header_enabled_setting.create_gui()
        with dpg.group(show=False) as self.header_bits:
            for setting in self.header_settings:
                DpgSetting.create(self.descriptors[setting]).create_gui()
        dpg.pop_container_stack()
            
    def __on_header_enabled_changed(self, key, new_value):
        dpg.configure_item(self.header_bits, show=bool(new_value))
            

class LogFormatSelectionPage(DpgWizardPageBasic):
    
    def __init__(self, descriptors: dict[str, ThreespaceSettingDescriptor], **kwargs):
        super().__init__(title="Format Selection", **kwargs)

    def create_view(self):
        dpg.push_container_stack(super().create_view())
        dpg.add_text("Yep")
        dpg.pop_container_stack()

class LogTriggerSelectionPage(DpgWizardPageBasic):
    
    def __init__(self, descriptors: dict[str, ThreespaceSettingDescriptor], **kwargs):
        super().__init__(title="Trigger Selection", **kwargs)

    def create_view(self):
        dpg.push_container_stack(super().create_view())
        dpg.add_text("Yep")
        dpg.pop_container_stack()

class DataLoggingConfigWizard(DpgWizard):
    
    def __init__(self, sensor: ThreespaceSensor):
        super().__init__(label="Data Logging Setup")

        descriptors = sensor.get_all_setting_descriptions()

        self.add_page(LogDataSelectionPage(descriptors))
        self.add_page(LogFormatSelectionPage(descriptors))
        self.add_page(LogTriggerSelectionPage(descriptors))

        self.set_page(0)


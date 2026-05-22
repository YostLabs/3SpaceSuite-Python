import dearpygui.dearpygui as dpg
from gui.setting_gui.setting_structures import DpgSetting
from gui.setting_gui.setting_structures_custom import *
from yostlabs.tss3 import ThreespaceSensor
from gui.core_ui import DpgWizard, StagedView

from typing import Callable

class ConfigWizard(DpgWizard):

    def __init__(self):
        super().__init__(always_centered=True, label="Data Logging Setup")

        self.page_index = -1
        self.pages: list[ConfigWizardPage] = []

        self.cur_window: ConfigWizardPage
        dpg.push_container_stack(self.modal)
        with dpg.child_window(width=480, height=380, border=False):
            self.title_text = dpg.add_text("Title", color=(120, 170, 255))
            dpg.add_separator()
            dpg.add_spacer(height=8)
            
            with dpg.child_window(height=-48, border=False) as self.page_space:
                pass
            self.set_page_destination(self.page_space)

            dpg.add_spacer(height=8)
            dpg.add_separator()
            self.footer = dpg.add_child_window(border=False)
            self.create_default_footer()
                    
        dpg.pop_container_stack()
    
    def create_default_footer(self):
        dpg.delete_item(self.footer, children_only=True)
        dpg.push_container_stack(self.footer)

        with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False, borders_innerV=False, borders_outerV=False):
            dpg.add_table_column()
            dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
            with dpg.table_row():
                dpg.add_table_cell()
                with dpg.group(horizontal=True):
                    self.back_button = dpg.add_button(label="Back", callback=self.on_back, width=70)
                    self.next_button = dpg.add_button(label="Next", callback=self.on_next, width=70)

        dpg.pop_container_stack()

    def go_next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.set_page(self.page_index + 1)
    
    def go_previous_page(self):
        if self.page_index > 0:
            self.set_page(self.page_index - 1)

    def set_page(self, page_index: int):
        if page_index < 0 or page_index >= len(self.pages):
            return
        self.page_index = page_index
        self.set_window(self.pages[page_index])

    def add_page(self, page: "ConfigWizardPage"):
        self.pages.append(page)
        page.wizard = self

    def set_window(self, window: "ConfigWizardPage"):
        super().set_window(window)
        if window is None:
            self.create_default_footer()
        else:
            if window.footer_override:
                dpg.delete_item(self.footer, children_only=True)
            else:
                self.create_default_footer()
                if self.page_index == len(self.pages) - 1 and window.next_button_label is None:
                    next_label = "Finish"
                else:
                    next_label = window.next_button_label or "Next"
                back_label = window.back_button_label or "Back"
                dpg.configure_item(self.next_button, label=next_label)
                dpg.configure_item(self.back_button, label=back_label)

            dpg.set_value(self.title_text, window.title)
            


    def on_next(self, sender, app_data, user_data):
        if self.cur_window is not None:
            self.cur_window.on_next()
        
        if self.page_index + 1 >= len(self.pages):
            self.finish()
            return
        self.set_page(self.page_index + 1)

    def on_back(self, sender, app_data, user_data):
        if self.cur_window is not None:
            self.cur_window.on_back()
        
        if self.page_index == 0:
            return
        self.set_page(self.page_index - 1)

    def finish(self):
        self.delete()


class ConfigWizardPage(StagedView):

    def __init__(self, title: str = "Title", next_button_label:str = None, back_button_label:str = None, footer_override=False):
        super().__init__()

        # This will be set by the add page call in the wizard.
        # This allows the page to call methods on the wizard such as go_next_page or 
        #   go_previous_page without needing to worry about how the page is being used
        self.wizard: ConfigWizard = None

        self.title = title
        self.next_button_label = next_button_label
        self.back_button_label = back_button_label
        self.footer_override = footer_override

    def on_next(self):
        pass

    def on_back(self):
        pass

class LogDataSelectionPage(ConfigWizardPage):

    def __init__(self, descriptors: dict[str, ThreespaceSettingDescriptor]):
        super().__init__(title="Data Selection")


        self.header_enabled_setting = DpgSetting.create(descriptors["log_header_enabled"])
        self.header_enabled_setting.on_change.subscribe(self.__on_header_enabled_changed)
        header_settings = ["header_status", "header_timestamp", "header_echo", "header_checksum", "header_serial", "header_length"]

        with dpg.stage() as self._stage_id:
            self.header_enabled_setting.create_gui()
            with dpg.group(show=False) as self.header_bits:
                for setting in header_settings:
                    DpgSetting.create(descriptors[setting]).create_gui()
    
    def __on_header_enabled_changed(self, key, new_value):
        dpg.configure_item(self.header_bits, show=bool(new_value))
            

class LogFormatSelectionPage(ConfigWizardPage):
    
    def __init__(self, descriptors: dict[str, ThreespaceSettingDescriptor]):
        super().__init__(title="Format Selection")

        with dpg.stage() as self._stage_id:
            dpg.add_text("Yep")

class LogTriggerSelectionPage(ConfigWizardPage):
    
    def __init__(self, descriptors: dict[str, ThreespaceSettingDescriptor]):
        super().__init__(title="Trigger Selection")

        with dpg.stage() as self._stage_id:
            dpg.add_text("Yep")

class DataLoggingConfigWizard(ConfigWizard):
    
    def __init__(self, sensor: ThreespaceSensor):
        super().__init__()

        descriptors = sensor.get_all_setting_descriptions()

        self.add_page(LogDataSelectionPage(descriptors))
        self.add_page(LogFormatSelectionPage(descriptors))
        self.add_page(LogTriggerSelectionPage(descriptors))

        self.set_page(0)

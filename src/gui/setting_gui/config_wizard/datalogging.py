import dearpygui.dearpygui as dpg
from datetime import datetime, timedelta
from typing import Any
from gui.setting_gui.setting_structures import DpgSetting
from gui.setting_gui.setting_structures_custom import *
from yostlabs.tss3 import ThreespaceSensor
from gui.core_ui import DpgWizard, DpgWizardPageBasic

from gui.setting_gui.setting_structures import DpgSettingMenu

DISABLED_ROW_THEME = None

def ensure_disabled_row_theme():
    global DISABLED_ROW_THEME
    if DISABLED_ROW_THEME is not None:
        return

    with dpg.theme() as DISABLED_ROW_THEME:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (145, 145, 145, 255))

        for component in [dpg.mvInputInt, dpg.mvInputFloat, dpg.mvInputDouble, dpg.mvInputText, dpg.mvCombo]:
            with dpg.theme_component(component):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (44, 44, 44, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (44, 44, 44, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (44, 44, 44, 255))

        with dpg.theme_component(dpg.mvCheckbox):
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (145, 145, 145, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (44, 44, 44, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (44, 44, 44, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (44, 44, 44, 255))

class DpgSettingWizardPageBasic(DpgWizardPageBasic):

    def __init__(self, title: str, **kwargs):
        super().__init__(title=title, **kwargs)
        self.setting_menu: DpgSettingMenu | None = None

class LogDataSelectionPage(DpgSettingWizardPageBasic):

    HEADER_SETTINGS = { "header_status": "Status",
                        "header_timestamp": "Timestamp",
                        "header_echo": "Echo",
                        "header_checksum": "Checksum",
                        "header_serial": "Serial #",
                        "header_length": "Length" }

    def __init__(self, sensor: ThreespaceSensor, descriptors: dict[str, ThreespaceSettingDescriptor], current_values: dict[str, Any] | None = None, **kwargs):
        super().__init__(title="Data Selection", **kwargs)

        self.descriptors = descriptors

        self.setting_menu = DpgSettingMenu(sensor)

        self.header_enabled_setting = DpgSetting.create(descriptors["log_header_enabled"])
        self.header_enabled_setting.on_change.subscribe(self.__on_header_enabled_changed)
        self.setting_menu.add_setting(self.header_enabled_setting)

        self.rate_setting = DpgSetting.create(descriptors["log_hz"])
        self.setting_menu.add_setting(self.rate_setting)

        self.log_slots_setting = DpgSetting.create(descriptors["log_slots"])
        self.setting_menu.add_setting(self.log_slots_setting)

        self.header_settings: list[tuple[str, DpgSetting]] = []

        for row_start in range(0, len(self.HEADER_SETTINGS), 3):
            for key in list(self.HEADER_SETTINGS.keys())[row_start:row_start + 3]:
                setting = DpgSetting.create(self.descriptors[key])
                label = self.HEADER_SETTINGS[key]
                self.header_settings.append((label, setting))
                self.setting_menu.add_setting(setting)

        self.setting_menu.reload_values(cache=False, validate=False, current_values=current_values)
        self.setting_menu.populate_all_setting_descriptions()

    def create_view(self):
        dpg.push_container_stack(super().create_view())

        # Header enabled checkbox
        with dpg.group(horizontal=True):
            self.header_enabled_setting.create_param_gui()
            text = dpg.add_text("Header Enabled")
            self.header_enabled_setting.init_gui(text)

        # 2-row x 3-column grid of header bit checkboxes, hidden until header is enabled
        with dpg.group(show=False) as self.header_bits:
            with dpg.table(header_row=False):
                dpg.add_table_column()
                dpg.add_table_column()
                dpg.add_table_column()
                for row_start in range(0, len(self.HEADER_SETTINGS), 3):
                    with dpg.table_row():
                        for label, setting in self.header_settings[row_start:row_start + 3]:
                            with dpg.table_cell():
                                with dpg.group(horizontal=True):
                                    setting.create_param_gui()
                                    text = dpg.add_text(label)
                                    setting.init_gui(text)

        dpg.add_separator()

        #Logging rate
        with dpg.group(horizontal=True):
            #Prevent the unit from rendering to show custom text instead
            self.rate_setting.descriptor.param_descriptors[0].unit = ""
            self.rate_setting.create_param_gui()
            text = dpg.add_text("Logging Rate (Hz)")
            self.rate_setting.description = self.rate_setting.description + \
            "\n\nNote: The actual logging rate may be lower than the configured rate if the "   \
            "sensor cannot keep up with the amount of data being logged. For higher data rates, "   \
            "it is recommended to set the data mode to binary, and/or increase the cpu_speed setting "  \
            "in the 'Power Management' section of the settings menu."

            self.rate_setting.create_help_tag()
            self.rate_setting.init_gui(text)

        dpg.add_separator()

        # Log slots selection
        self.log_slots_setting.create_gui(help_tag=False)

        dpg.pop_container_stack()

        #Update the state of the header bit checkboxes based on the current value of the header enabled setting
        self.__on_header_enabled_changed(None, self.header_enabled_setting.get_value())

    def on_next(self):
        all_valid = self.setting_menu.validate_all()
        if not all_valid:
            return False
        all_applied = self.setting_menu.apply_all(dirty_only=False, cache_values=False)
        if not all_applied:
            return False
        return True

    def __on_header_enabled_changed(self, key, new_value):
        dpg.configure_item(self.header_bits, show=bool(new_value))

    def delete(self):
        self.setting_menu.cleanup()
        super().delete()
            

class LogFormatSelectionPage(DpgSettingWizardPageBasic):
    
    FRIENDLY_LABELS = {
        "log_style": "Log Style",
        "log_periodic_capture_time": "Capture Time (s)",
        "log_periodic_rest_time": "Rest Time (s)",
        "log_base_filename": "Base Filename",
        "log_folder_mode": "Folder Mode",
        "log_file_mode": "File Mode",
        "log_data_mode": "Data Mode",
    }

    def __init__(self, sensor: ThreespaceSensor, descriptors: dict[str, ThreespaceSettingDescriptor], current_values: dict[str, Any] | None = None, **kwargs):
        super().__init__(title="Format Selection", **kwargs)
        self.descriptors = descriptors

        # Settings
        self.setting_menu = DpgSettingMenu(sensor)

        self.log_style_setting = DpgSetting.create(descriptors["log_style"])
        self.log_style_setting.on_change.subscribe(self.__on_log_style_changed)
        self.log_style_setting.on_change.subscribe(self.__on_filename_related_setting_changed)
        self.setting_menu.add_setting(self.log_style_setting)

        self.log_periodic_capture_setting = DpgSetting.create(descriptors["log_periodic_capture_time"])
        self.setting_menu.add_setting(self.log_periodic_capture_setting)
        self.log_rest_time_setting = DpgSetting.create(descriptors["log_periodic_rest_time"])
        self.setting_menu.add_setting(self.log_rest_time_setting)

        self.log_base_filename_setting = DpgSetting.create(descriptors["log_base_filename"])
        self.log_base_filename_setting.on_change.subscribe(self.__on_filename_related_setting_changed)
        self.setting_menu.add_setting(self.log_base_filename_setting)

        self.log_folder_mode_setting = DpgSetting.create(descriptors["log_folder_mode"])
        self.log_folder_mode_setting.on_change.subscribe(self.__on_filename_related_setting_changed)
        self.setting_menu.add_setting(self.log_folder_mode_setting)

        self.log_file_mode_setting = DpgSetting.create(descriptors["log_file_mode"])
        self.log_file_mode_setting.on_change.subscribe(self.__on_filename_related_setting_changed)
        self.setting_menu.add_setting(self.log_file_mode_setting)

        self.log_data_mode_setting = DpgSetting.create(descriptors["log_data_mode"])
        self.log_data_mode_setting.on_change.subscribe(self.__on_filename_related_setting_changed)
        self.setting_menu.add_setting(self.log_data_mode_setting)

        self.setting_menu.populate_all_setting_descriptions()

        self.setting_menu.reload_values(cache=False, validate=False, current_values=current_values)

        # For hiding/showing conditional fields
        self.periodic_group = None
        self.log_file_mode_row = None

    def create_view(self):
        ensure_disabled_row_theme()
        dpg.push_container_stack(super().create_view())

        # Log Style
        with dpg.group(horizontal=True):
            self.log_style_setting.create_param_gui()
            text = dpg.add_text(self.FRIENDLY_LABELS["log_style"])
            self.log_style_setting.create_help_tag()
            self.log_style_setting.init_gui(text)

        dpg.add_spacer(height=6)

        # Periodic Capture (conditional)
        with dpg.group() as self.periodic_group:
            #Capture Time
            with dpg.group(horizontal=True):
                self.log_periodic_capture_setting.descriptor.param_descriptors[0].unit = ""
                self.log_periodic_capture_setting.create_param_gui()
                text = dpg.add_text(self.FRIENDLY_LABELS["log_periodic_capture_time"])
                self.log_periodic_capture_setting.create_help_tag()
                self.log_periodic_capture_setting.init_gui(text)

            #Rest time
            with dpg.group(horizontal=True):
                self.log_rest_time_setting.descriptor.param_descriptors[0].unit = ""
                self.log_rest_time_setting.create_param_gui()
                text = dpg.add_text(self.FRIENDLY_LABELS["log_periodic_rest_time"])
                self.log_rest_time_setting.create_help_tag()
                self.log_rest_time_setting.init_gui(text)

        dpg.add_separator()

        # Folder Mode
        with dpg.group(horizontal=True):
            self.log_folder_mode_setting.create_param_gui()
            text = dpg.add_text(self.FRIENDLY_LABELS["log_folder_mode"])
            self.log_folder_mode_setting.create_help_tag()
            self.log_folder_mode_setting.init_gui(text)

        # File Mode
        with dpg.group(horizontal=True) as self.log_file_mode_row:
            self.log_file_mode_setting.create_param_gui()
            text = dpg.add_text(self.FRIENDLY_LABELS["log_file_mode"])
            self.log_file_mode_setting.create_help_tag()
            self.log_file_mode_setting.init_gui(text)

        # Data Mode
        with dpg.group(horizontal=True):
            self.log_data_mode_setting.create_param_gui()
            text = dpg.add_text(self.FRIENDLY_LABELS["log_data_mode"])
            self.log_data_mode_setting.create_help_tag()
            self.log_data_mode_setting.init_gui(text)

        dpg.add_spacer(height=6)

        # Base Filename
        with dpg.group(horizontal=True):
            self.log_base_filename_setting.create_param_gui()
            text = dpg.add_text(self.FRIENDLY_LABELS["log_base_filename"])
            self.log_base_filename_setting.create_help_tag()
            self.log_base_filename_setting.init_gui(text)

        dpg.add_spacer(height=6)

        with dpg.group(horizontal=True):
            dpg.add_text("Example Files:")
            with dpg.group() as self.filename_example_group:
                dpg.add_text("data0.csv") #Placeholder, updated in __update_filename_example

        dpg.pop_container_stack()

        self.__update_conditional_fields(self.log_style_setting.get_value())
        self.__update_filename_example()

    def on_next(self):
        all_valid = self.setting_menu.validate_all()
        if not all_valid:
            return False
        all_applied = self.setting_menu.apply_all(dirty_only=False, cache_values=False)
        if not all_applied:
            return False
        return True

    def __on_filename_related_setting_changed(self, key, new_value):
        self.__update_filename_example()

    def __update_filename_example(self):
        dpg.delete_item(self.filename_example_group, children_only=True)
        dpg.push_container_stack(self.filename_example_group)
        
        extension = ".csv" if self.log_data_mode_setting.get_value() == 1 else ".bin"
        basename = self.log_base_filename_setting.get_value()

        #Session Number
        if self.log_folder_mode_setting.get_value() == 0:
            session_first_folder= "session-01"
            session_second_folder = "session-02"       
        else: #Date Time
            now = datetime.now()
            session_first_folder = now.strftime("%Y-%m-%d_%H-%M-%S")
            session_second_folder = (now + timedelta(days=1, hours=12, minutes=18, seconds=27)).strftime("%Y-%m-%d_%H-%M-%S")
             
        dpg.add_text(f"{session_first_folder}/{basename}0{extension}", wrap=0)
        #Log Style = Periodic && New File Mode
        if self.log_style_setting.get_value() == 1 and self.log_file_mode_setting.get_value() == 1:
            dpg.add_text(f"{session_first_folder}/{basename}1{extension}", wrap=0)
        dpg.add_text(f"{session_second_folder}/{basename}0{extension}", wrap=0)
        dpg.add_text("...")
        
        dpg.pop_container_stack()

    def __on_log_style_changed(self, key, new_value):
        self.__update_conditional_fields(new_value)

    def __update_conditional_fields(self, log_style_value):
        #If using periodic mode, show the periodic capture/rest time settings. Otherwise, hide them.
        is_periodic = (log_style_value == 1)
        dpg.configure_item(self.periodic_group, show=is_periodic)
        self.log_file_mode_setting.set_enabled(is_periodic)
        if self.log_file_mode_row is not None:
            dpg.configure_item(self.log_file_mode_row, enabled=is_periodic)
            dpg.bind_item_theme(self.log_file_mode_row, None if is_periodic else DISABLED_ROW_THEME)

    def delete(self):
        self.setting_menu.cleanup()
        super().delete()

class LogTriggerSelectionPage(DpgSettingWizardPageBasic):

    START_EVENT_DEPENDENCIES = {
        1: ["log_start_motion_threshold"],
    }

    STOP_EVENT_DEPENDENCIES = {
        1: ["log_stop_motion_threshold", "log_stop_motion_delay"],
        3: ["log_stop_duration"],
        4: ["log_stop_count"],
        5: ["log_stop_period_count"],
    }

    FRIENDLY_LABELS = {
        "log_start_motion_threshold": "Motion Threshold",
        "log_stop_motion_threshold": "Motion Threshold",
        "log_stop_motion_delay": "Motion Delay (s)",
        "log_stop_duration": "Duration (s)",
        "log_stop_count": "Sample Count",
        "log_stop_period_count": "Period Count",
    }

    START_DEPENDENT_ORDER = [
        "log_start_motion_threshold",
    ]

    STOP_DEPENDENT_ORDER = [
        "log_stop_motion_threshold",
        "log_stop_motion_delay",
        "log_stop_duration",
        "log_stop_count",
        "log_stop_period_count",
    ]
    
    def __init__(self, sensor: ThreespaceSensor, descriptors: dict[str, ThreespaceSettingDescriptor], current_values: dict[str, Any] | None = None, **kwargs):
        super().__init__(title="Trigger Selection", **kwargs)

        self.descriptors = descriptors

        self.setting_menu = DpgSettingMenu(sensor)

        self.start_event_setting = DpgSetting.create(descriptors["log_start_event"])
        self.start_event_setting.on_change.subscribe(self.__on_start_event_changed)
        self.setting_menu.add_setting(self.start_event_setting)

        self.stop_event_setting = DpgSetting.create(descriptors["log_stop_event"])
        self.stop_event_setting.on_change.subscribe(self.__on_stop_event_changed)
        self.setting_menu.add_setting(self.stop_event_setting)

        self.start_dependent_settings: dict[str, DpgSetting] = {}
        for key in self.START_DEPENDENT_ORDER:
            #Don't want to display the units over the custom labels, so clear the unit text
            setting = DpgSetting.create(descriptors[key])
            self.start_dependent_settings[key] = setting
            self.setting_menu.add_setting(setting)

        self.stop_dependent_settings: dict[str, DpgSetting] = {}
        for key in self.STOP_DEPENDENT_ORDER:
            setting = DpgSetting.create(descriptors[key])
            self.stop_dependent_settings[key] = setting
            self.setting_menu.add_setting(setting)

        self.start_dependent_rows: dict[str, int] = {}
        self.stop_dependent_rows: dict[str, int] = {}

        self.setting_menu.reload_values(cache=False, validate=False, current_values=current_values)
        self.setting_menu.populate_all_setting_descriptions()

    def create_view(self):
        ensure_disabled_row_theme()
        dpg.push_container_stack(super().create_view())
        
        self.start_event_setting.create_gui(help_tag=False)
        if self.start_event_setting._key_label is not None:
            dpg.set_value(self.start_event_setting._key_label, "Enabled Start Events")
        dpg.add_spacer(height=6)
        for key in self.START_DEPENDENT_ORDER:
            setting = self.start_dependent_settings[key]
            with dpg.group() as row:
                with dpg.group(horizontal=True):
                    #Don't want to display the units over the custom labels, so clear the unit text
                    setting.descriptor.param_descriptors[0].unit = "" 
                    setting.create_param_gui()
                    text = dpg.add_text(self.FRIENDLY_LABELS.get(key, key))
                    setting.create_help_tag()
                    setting.init_gui(text)
            self.start_dependent_rows[key] = row

        dpg.add_spacer(height=6)
        dpg.add_separator()

        self.stop_event_setting.create_gui(help_tag=False)
        if self.stop_event_setting._key_label is not None:
            dpg.set_value(self.stop_event_setting._key_label, "Enabled Stop Events")
        dpg.add_spacer(height=6)
        for key in self.STOP_DEPENDENT_ORDER:
            setting = self.stop_dependent_settings[key]
            with dpg.group() as row:
                with dpg.group(horizontal=True):
                    #Don't want to display the units over the custom labels, so clear the unit text
                    setting.descriptor.param_descriptors[0].unit = "" 
                    setting.create_param_gui()
                    text = dpg.add_text(self.FRIENDLY_LABELS.get(key, key))
                    setting.create_help_tag()
                    setting.init_gui(text)
            self.stop_dependent_rows[key] = row

        dpg.pop_container_stack()

        self.__update_start_event_enabled_state(self.start_event_setting.get_value())
        self.__update_stop_event_enabled_state(self.stop_event_setting.get_value())

    def on_next(self):
        all_valid = self.setting_menu.validate_all()
        if not all_valid:
            return False
        all_applied = self.setting_menu.apply_all(dirty_only=False, cache_values=False)
        if not all_applied:
            return False
        return True

    def __on_start_event_changed(self, key: str, new_value: str):
        self.__update_start_event_enabled_state(new_value)

    def __on_stop_event_changed(self, key: str, new_value: str):
        self.__update_stop_event_enabled_state(new_value)

    def __update_start_event_enabled_state(self, start_event_value: str):
        self.__update_event_enabled_state(start_event_value, self.START_EVENT_DEPENDENCIES, self.start_dependent_settings, self.start_dependent_rows)

    def __update_stop_event_enabled_state(self, stop_event_value: str):
        self.__update_event_enabled_state(stop_event_value, self.STOP_EVENT_DEPENDENCIES, self.stop_dependent_settings, self.stop_dependent_rows)

    def __update_event_enabled_state(self, event_value: str, dependencies: dict[int, list[str]], dependent_settings: dict[str, DpgSetting], dependent_rows: dict[str, int]):
        enabled_events = self.__parse_event_values(event_value)
        enabled_keys = set()
        for event in enabled_events:
            enabled_keys.update(dependencies.get(event, []))

        for key, setting in dependent_settings.items():
            is_enabled = key in enabled_keys
            setting.set_enabled(is_enabled)
            row = dependent_rows.get(key)
            if row is not None:
                dpg.bind_item_theme(row, None if is_enabled else DISABLED_ROW_THEME)

    def __parse_event_values(self, value: str) -> set[int]:
        if value is None or value == "":
            return set()
        
        values = []
        for part in value.split(','):
            part = part.strip()
            if part == "":
                continue
            try:
                values.append(int(part))
            except ValueError:
                continue
        return set(values)        

    def delete(self):
        self.setting_menu.cleanup()
        super().delete()

class DataLoggingConfigWizard(DpgWizard):
    
    def __init__(self, sensor: ThreespaceSensor, on_completion=None):
        #Sadly, this can't be modal because it uses the FilteredDropdown which
        #creates a floating window for the dropdown list. This window does not work
        #when there is a modal window present.
        super().__init__(label="Data Logging Setup", 
                         min_size=(550, 525), max_size=(550, 800),
                         modal=False, no_close=False,
                         on_close=self.__on_window_closed)

        self.sensor = sensor
        self.on_completion = on_completion
        self.initial_tracked_values: dict[str, Any] = {}

        descriptors = sensor.get_all_setting_descriptions()
        current_values = sensor.readAllWritableSettings()

        data_selection_page = LogDataSelectionPage(sensor, descriptors, current_values=current_values)
        format_selection_page = LogFormatSelectionPage(sensor, descriptors, current_values=current_values)
        trigger_selection_page = LogTriggerSelectionPage(sensor, descriptors, current_values=current_values)

        self.add_page(data_selection_page)
        self.add_page(format_selection_page)
        self.add_page(trigger_selection_page)
        
        setting_pages: list[DpgSettingWizardPageBasic] = [data_selection_page, format_selection_page, trigger_selection_page]

        #Save off the initial values of settings affected by this wizard so they can be restored if the user cancels.
        tracked_keys = set()
        for page in setting_pages:
            tracked_keys.update(setting.descriptor.key for setting in page.setting_menu.settings)
        self.initial_tracked_values = {key: current_values[key] for key in tracked_keys if key in current_values}

        self.set_page(0)

    def finish(self):
        if self.on_completion is not None:
            self.on_completion(True)
        return super().finish()

    def cancel(self):
        self.__restore_initial_settings()
        if self.on_completion is not None:
            self.on_completion(False)
        super().cancel()
        

    #This only occurs on the X being pressed, not on the window closing from the Finish or Cancel buttons
    def __on_window_closed(self, sender, app_data, user_data):
        self.cancel()

    def __restore_initial_settings(self):
        for key, value in self.initial_tracked_values.items():
            try:
                self.sensor.write_settings(**{key: value})
            except Exception:
                pass


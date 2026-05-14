import dearpygui.dearpygui as dpg
from dpg_ext.input_fields import InputIntPy, InputFloatPy, InputNumericPy

from yostlabs.tss3 import ThreespaceSensor
from yostlabs.tss3.settings import ThreespaceSettingDescriptor, ThreespaceSettingParamDescriptor, ThreespaceSettingParamValidationMode

from managers.documentation_manager import SettingsDocumentationTable

import re

from abc import ABC, abstractmethod
from typing import Any

INVALID_FIELD_THEME = None
INVALID_SECTION_THEME = None
_RESET_THEME = None

def init_themes():
    global INVALID_FIELD_THEME, INVALID_SECTION_THEME, _RESET_THEME
    with dpg.theme() as INVALID_FIELD_THEME:
        for component in [dpg.mvInputText, dpg.mvCombo, dpg.mvCheckbox, dpg.mvChildWindow]:
            with dpg.theme_component(component):
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 2)
                dpg.add_theme_color(dpg.mvThemeCol_Border, (220, 40, 40, 255))

    with dpg.theme() as INVALID_SECTION_THEME:

        with dpg.theme_component(dpg.mvCollapsingHeader):
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 2)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (220, 40, 40, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (220, 40, 40, 255))

    # Resets text color to default for all widget types.
    # Bound to the children container of a section when the section is marked invalid,
    # so the red text from INVALID_SECTION_THEME does not cascade to child widgets.
    with dpg.theme() as _RESET_THEME:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (78, 78, 78, 255))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)

_SETTING_REGISTRY: list[tuple[re.Pattern, type["DpgSetting"]]] = []

def register_setting(pattern: str):
    """Decorator to register a custom DpgSetting subclass for a setting key.
    'pattern' is a regex string matched against the full concrete key.
    Use anchors (^ $) when an exact match is required."""
    print("REGISTERING SETTING", pattern)
    compiled = re.compile(pattern)
    def decorator(cls):
        _SETTING_REGISTRY.append((compiled, cls))
        return cls
    return decorator

class DpgSetting:

    def __init__(self, descriptor: ThreespaceSettingDescriptor):
        self.descriptor = descriptor
        self.params: list[DpgSettingParamField] = [
            DpgSettingParamField.create(param_desc) for param_desc in descriptor.param_descriptors
        ]
        self.description = None

        self._tmp_value = None
        self._ui_initialized = False

    def _add_help_tag(self):
        """Add the '?' help tooltip next to the current cursor position, if a description is set."""
        if self.description:
            help_tag = dpg.add_text(" ?", color=(120, 170, 255))
            with dpg.tooltip(parent=help_tag):
                dpg.add_text(self.description, wrap=700)

    def create_gui(self):
        with dpg.group(horizontal=True):
            dpg.add_text(self.descriptor.key)
            for param in self.params:
                param.create_gui()
            self._add_help_tag()
        self._ui_initialized = True
        if self._tmp_value is not None:
            self.set_value(self._tmp_value)

    def get_value(self):
        values = [param.get_value() for param in self.params]
        if len(values) == 1:
            return values[0]
        return values
    
    def set_value(self, value: Any):
        if not isinstance(value, (list, tuple)):
            value = [value]
        if not self._ui_initialized:
            self._tmp_value = value
        else:
            for param, val in zip(self.params, value):
                param.set_value(val)
    
    def set_description(self, description: str):
        self.description = description

    def pre_validate(self):
        """
        Validation performed before attempting to apply settings based on known constraints from the descriptor.
        """
        all_valid = True
        for param in self.params:
            try:
                valid = param.validate()
            except ValueError as e:
                print(e)
                valid = False
            all_valid = all_valid and valid
            param.mark_invalid(not valid)
        return all_valid

    def mark_invalid(self, is_invalid: bool):
        for param in self.params:
            param.mark_invalid(is_invalid)

    def apply(self, sensor: ThreespaceSensor):
        try:
            err, num_successes = sensor.write_settings(**{self.descriptor.key: self.get_value()})
        except:
            err = -256
        self.mark_invalid(err != 0)
        return not err

    @staticmethod
    def create(descriptor: ThreespaceSettingDescriptor):
        for pattern, cls in _SETTING_REGISTRY:
            if pattern.match(descriptor.key):
                return cls(descriptor)
        return DpgSetting(descriptor)

class DpgSettingParamField(ABC):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        self.descriptor = descriptor

    @staticmethod
    def create(descriptor: ThreespaceSettingParamDescriptor):
        if descriptor.validation_mode == ThreespaceSettingParamValidationMode.ENUM:
            return DpgSettingParamEnum(descriptor)
        elif descriptor.validation_mode == ThreespaceSettingParamValidationMode.BOOL:
            return DpgSettingParamBool(descriptor)
        else:
            if descriptor.type is int:
                return DpgSettingParamInt(descriptor)
            elif descriptor.type is float:
                return DpgSettingParamFloat(descriptor)
            elif descriptor.type is str:
                return DpgSettingParamFreeform(descriptor)
            else:
                print(f"Unsupported setting parameter type for key {descriptor.setting.key}: {descriptor.type}, defaulting to freeform input.")
                return DpgSettingParamFreeform(descriptor)

    def validate(self):
        return self.descriptor.validate(self.get_value())

    @abstractmethod
    def get_value(self):
        pass

    @abstractmethod
    def set_value(self, value: Any):
        pass

    @abstractmethod
    def create_gui(self):
        pass
    
    @abstractmethod
    def mark_invalid(self, is_invalid: bool):
        pass

class DpgSettingParamEnum(DpgSettingParamField):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.dropdown = None

    def create_gui(self):
        self.dropdown = dpg.add_combo(self.descriptor.valid_value_keys(), width=100)

    def set_value(self, value):
        return dpg.set_value(self.dropdown, self.descriptor.value_to_string(value))

    def get_value(self):
        selected = dpg.get_value(self.dropdown)
        return self.descriptor.string_to_value(selected)
    
    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.bind_item_theme(self.dropdown, INVALID_FIELD_THEME)
        else:
            dpg.bind_item_theme(self.dropdown, None)

class DpgSettingParamBool(DpgSettingParamField):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.checkbox = None

    def create_gui(self):
        self.checkbox = dpg.add_checkbox()

    def set_value(self, value):
        dpg.set_value(self.checkbox, bool(value))

    def get_value(self):
        return 1 if dpg.get_value(self.checkbox) else 0

    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.bind_item_theme(self.checkbox, INVALID_FIELD_THEME)
        else:
            dpg.bind_item_theme(self.checkbox, None)

class DpgSettingParamNumeric(DpgSettingParamField):
    """Shared base for numeric input fields backed by InputIntPy/InputFloatPy."""

    INPUT_CLASS: type[InputNumericPy] = None  # override in subclass
    CAST = None         # override in subclass

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.input = None

    def create_gui(self):
        DEFAULT_WIDTH = 100
        self.input = self.INPUT_CLASS(width=DEFAULT_WIDTH)
        if self.descriptor.validation_mode == ThreespaceSettingParamValidationMode.RANGE:
            self.input.set_range(self.descriptor.min_value, self.descriptor.max_value)
            required_width = self.input.get_required_width_by_current_range(padding=0)
            if required_width is not None:
                self.input.set_width(max(DEFAULT_WIDTH, required_width))
        if self.descriptor.unit:
            dpg.add_text(f"{self.descriptor.unit}")

    def set_value(self, value):
        self.input.set_value(self.CAST(value))

    def get_value(self):
        return self.input.get_value()

    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.bind_item_theme(self.input.field, INVALID_FIELD_THEME)
        else:
            dpg.bind_item_theme(self.input.field, None)

class DpgSettingParamInt(DpgSettingParamNumeric):
    INPUT_CLASS = InputIntPy
    CAST = int

    def create_gui(self):
        super().create_gui()
        self.input: InputIntPy
        if self.descriptor.preferred_display_mode == "hex":
            self.input.set_display_mode("hex")

class DpgSettingParamFloat(DpgSettingParamNumeric):
    INPUT_CLASS = InputFloatPy
    CAST = float

class DpgSettingParamFreeform(DpgSettingParamField):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.input = None

    def create_gui(self):
        self.input = dpg.add_input_text(width=100)
        if self.descriptor.unit:
            dpg.add_text(f"{self.descriptor.unit}")

    def set_value(self, value):
        dpg.set_value(self.input, self.descriptor.value_to_string(value, suffix=False))

    def get_value(self):
        text = dpg.get_value(self.input)
        return self.descriptor.string_to_value(text)

    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.bind_item_theme(self.input, INVALID_FIELD_THEME)
        else:
            dpg.bind_item_theme(self.input, None)

def get_subkey(pattern_key: str, concrete_key: str) -> str | None:
    """Given a pattern like 'calib_mat_accel%d' and a concrete key like 'calib_mat_accel3',
    returns the subkey/component name, e.g. 'accel3'."""
    if "%d" not in pattern_key:
        return None
    prefix, _, suffix = pattern_key.partition("%d")
    # The component type is the last underscore-separated segment of the prefix
    component_type = prefix.rsplit("_", 1)[-1]  # e.g. "accel"
    # The digits are whatever sits between prefix and suffix in the concrete key
    digits = concrete_key[len(prefix): len(concrete_key) - len(suffix) if suffix else None]
    return component_type + digits  # e.g. "accel3"

class DpgSettingMenu:

    def __init__(self, sensor: ThreespaceSensor):
        #Sections will be displayed in the order of this list if they exist.
        #Any additional sections will be displayed after in an undefined order.
        self.section_order = [ 
            "System", 
            "Power Management", 
            "Streaming",
            "Data Logger",
            "Components",
            "Filter", 
            "Embedded", 
            "Battery", 
            "BLE", 
            "GPS",
            "Debug", 
            "EEPTS",
        ]

        self.sections: dict[str, dict[str, dict[str, int]] | dict[str, list[DpgSetting]]] = {}
        self.settings: list[DpgSetting] = []
        self.documentation = SettingsDocumentationTable()

        self.sensor = sensor

    def __update_section_validity_theme(self, section_name: str):
        if section_name not in self.sections:
            return
        section = self.sections[section_name]
        is_invalid = not section["all_valid"]
        if is_invalid:
            dpg.bind_item_theme(section["gui"]["header"], INVALID_SECTION_THEME)
            dpg.bind_item_theme(section["gui"]["primary"], _RESET_THEME)
            dpg.bind_item_theme(section["gui"]["secondary"], _RESET_THEME)
        else:
            dpg.bind_item_theme(section["gui"]["header"], None)
            dpg.bind_item_theme(section["gui"]["primary"], None)
            dpg.bind_item_theme(section["gui"]["secondary"], None)

    def set_section_invalid(self, section_name: str, is_invalid: bool):
        if section_name not in self.sections:
            return
        self.sections[section_name]["all_valid"] = not is_invalid
        self.__update_section_validity_theme(section_name)

    def add_section(self, name: str):
        if name in self.sections:
            return
        self.sections[name] = { "gui": {"header": None, "primary": None, "secondary": None }, "settings": [], "all_valid": True }

    def add_item(self, category: str, descriptor: ThreespaceSettingDescriptor, value: Any, description: str | None):
        if category not in self.sections:
            self.add_section(category)
        setting = DpgSetting.create(descriptor)
        setting.set_value(value)
        setting.set_description(description)
        self.sections[category]["settings"].append(setting)
        self.settings.append(setting)

    def create_hierarchy(self):
        #Create all the section headers first to ensure correct ordering.
        for section in self.section_order:
            self.add_section(section)

        descriptors = self.sensor.get_all_setting_descriptions()
        writeable_settings = self.sensor.readAllWritableSettings()
        writeable_settings.pop("cat", None)

        for key, value in writeable_settings.items():
            desc = descriptors[key]
            try:
                doc_row = self.documentation[key]
                category = doc_row["category"]
                description = doc_row["description"]
            except KeyError:
                category = "Uncategorized"
                description = None
            
            self.add_item(category, desc, value, description)

    def create_gui(self):
        for section in self.sections:
            header = dpg.add_collapsing_header(label=section, default_open=False, show=False)
            primary = dpg.add_group(parent=header)
            secondary = dpg.add_group(parent=header)
            self.sections[section]["gui"]["header"] = header
            self.sections[section]["gui"]["primary"] = primary
            self.sections[section]["gui"]["secondary"] = secondary
            self.__update_section_validity_theme(section)

            for setting in self.sections[section]["settings"]:
                subsection = "primary"
                try:
                    documentation = self.documentation[setting.descriptor.key]
                    if "%d" in documentation["key"]:
                        subsection = get_subkey(documentation["key"], setting.descriptor.key) or "primary"
                        if subsection not in self.sections[section]["gui"]:
                            secondary = self.sections[section]["gui"]["secondary"]
                            self.sections[section]["gui"][subsection] = dpg.add_tree_node(label=subsection, parent=secondary, default_open=True)
                except KeyError:
                    pass
                dpg.show_item(self.sections[section]["gui"]["header"])
                dpg.push_container_stack(self.sections[section]["gui"][subsection])
                setting.create_gui()
                dpg.pop_container_stack()
    
    def validate_all(self):
        all_valid = True
        for name, section in self.sections.items():
            section["all_valid"] = True
            for setting in section["settings"]:
                valid = setting.pre_validate()
                if not valid:
                    print(f"Invalid setting: {setting.descriptor.key} in section {name}")
                section["all_valid"] = section["all_valid"] and valid
                all_valid = all_valid and valid
            self.__update_section_validity_theme(name)
        print("All Valid:", all_valid)
        return all_valid
    
    def apply_all(self):
        all_success = True
        for name, section in self.sections.items():
            section["all_valid"] = True
            for setting in section["settings"]:
                success = setting.apply(self.sensor)
                if not success:
                    print(f"Failed to apply setting: {setting.descriptor.key} in section {name}")
                all_success = all_success and success
                section["all_valid"] = section["all_valid"] and success
            self.__update_section_validity_theme(name)
        return all_success

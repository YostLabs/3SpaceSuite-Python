import dearpygui.dearpygui as dpg
from dpg_ext.input_fields import InputIntPy, InputFloatPy, InputNumericPy

from yostlabs.tss3 import ThreespaceSensor
from yostlabs.tss3.settings import ThreespaceSettingDescriptor, ThreespaceSettingParamDescriptor, ThreespaceSettingParamValidationMode

from managers.documentation_manager import SettingsDocumentationTable
from utility import Callback

import re

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import data_charts  # For loading stream/log slot options from the sensor

INVALID_FIELD_THEME = None
INVALID_SECTION_THEME = None
_RESET_THEME = None
CACHED_VALUE_THEME = None
CACHED_VALUE_SECTION_THEME = None

INVALID_COLOR = (220, 40, 40, 255)
DIRTY_COLOR = (255, 220, 50, 255)

def init_themes():
    global INVALID_FIELD_THEME, INVALID_SECTION_THEME, _RESET_THEME, CACHED_VALUE_THEME, CACHED_VALUE_SECTION_THEME
    with dpg.theme(label="Invalid Field Theme") as INVALID_FIELD_THEME:
        for component in [dpg.mvInputText, dpg.mvCombo, dpg.mvCheckbox, dpg.mvChildWindow]:
            with dpg.theme_component(component):
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 2)
                dpg.add_theme_color(dpg.mvThemeCol_Border, INVALID_COLOR)

    with dpg.theme(label="Invalid Section Theme") as INVALID_SECTION_THEME:

        with dpg.theme_component(dpg.mvCollapsingHeader):
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 2)
            dpg.add_theme_color(dpg.mvThemeCol_Border, INVALID_COLOR)
            dpg.add_theme_color(dpg.mvThemeCol_Text, INVALID_COLOR)

    # Resets text color to default for all widget types.
    # Bound to the children container of a section when the section is marked invalid,
    # so the red text from INVALID_SECTION_THEME does not cascade to child widgets.
    with dpg.theme(label="Reset Theme") as _RESET_THEME:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (78, 78, 78, 255))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)

    with dpg.theme(label="Cached Value Section Theme") as CACHED_VALUE_SECTION_THEME:
        with dpg.theme_component(dpg.mvCollapsingHeader):
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 2)
            dpg.add_theme_color(dpg.mvThemeCol_Border, DIRTY_COLOR)
            dpg.add_theme_color(dpg.mvThemeCol_Text, DIRTY_COLOR)

    with dpg.theme(label="Cached Value Theme") as CACHED_VALUE_THEME:
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, DIRTY_COLOR)

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
        self._cached_value = None
        self._key_label = None
        self._ui_initialized = False
        self.on_change: Callback[[str, Any], None] = Callback()
        for param in self.params:
            param.on_change.subscribe(self._on_param_changed)

    def create_help_tag(self):
        """Add the '?' help tooltip next to the current cursor position, if a description is set."""
        if self.description:
            help_tag = dpg.add_text(" ?", color=(120, 170, 255))
            with dpg.tooltip(parent=help_tag):
                dpg.add_text(self.description, wrap=700)

    def create_gui(self):
        with dpg.group(horizontal=True):
            label_text = dpg.add_text(self.descriptor.key)
            self.create_param_gui()
            self.create_help_tag()

        self.init_gui(label_text)

        self._ui_initialized = True
        if self._tmp_value is not None:
            self.set_value(self._tmp_value)
            self._tmp_value = None

    def create_param_gui(self):
        for param in self.params:
            param.create_gui()

    def init_gui(self, label_text):
        """
        A way of assigning the GUI elements to the required variables after creation.
        This can be used to manually create the gui instead of calling create_gui and 
        then assign the UI elements.
        """
        self._key_label = label_text


    def _on_param_changed(self, param: "DpgSettingParamField", value: Any):
        """Called when any param changes; fires the setting-level on_change callback."""
        self._update_dirty_theme()
        self.on_change._notify(self.descriptor.key, self.get_value())

    def get_value(self):
        if self._tmp_value is not None:
            return self._tmp_value
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

    def cache_value(self):
        """Snapshot the current value as the cached (last-applied) value and update the dirty indicator."""
        self._cached_value = self.get_value()
        self._update_dirty_theme()

    def is_dirty(self) -> bool:
        """Return True if the current UI value differs from the cached value."""
        if self._cached_value is None:
            return False
        return self.get_value() != self._cached_value

    def _update_dirty_theme(self, *args):
        """Color the key label yellow when dirty, white when clean."""
        if self._key_label is None:
            return
        if self.is_dirty():
            dpg.bind_item_theme(self._key_label, CACHED_VALUE_THEME)
        else:
            dpg.bind_item_theme(self._key_label, None)

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
        if not err:
            self.cache_value()
        return not err

    def set_enabled(self, enabled: bool):
        """Enable or disable all param input fields for this setting."""
        for param in self.params:
            param.set_enabled(enabled)

    @staticmethod
    def create(descriptor: ThreespaceSettingDescriptor):
        for pattern, cls in _SETTING_REGISTRY:
            if pattern.match(descriptor.key):
                return cls(descriptor)
        return DpgSetting(descriptor)

class DpgSettingParamField(ABC):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        self.descriptor = descriptor
        self.on_change: Callback[[str, Any], None] = Callback()

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
                print(f"Unsupported setting parameter type: {descriptor.type}, defaulting to freeform input.")
                return DpgSettingParamFreeform(descriptor)

    def validate(self):
        return self.descriptor.validate(self.get_value())

    def _dpg_callback(self, sender, app_data):
        self._generic_callback()
    
    def _generic_callback(self, *args, **kwargs):
        self.on_change._notify(self, self.get_value())

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

    @abstractmethod
    def set_enabled(self, enabled: bool):
        pass

class DpgSettingParamEnum(DpgSettingParamField):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.dropdown = None

    def create_gui(self):
        width = max([dpg.get_text_size(label)[0] for label in self.descriptor.valid_value_keys()])
        width = max(width, 100) + 30 #Extra space is for the dropdown arrow
        self.dropdown = dpg.add_combo(self.descriptor.valid_value_keys(), width=width,
                                      callback=self._dpg_callback)

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

    def set_enabled(self, enabled: bool):
        dpg.configure_item(self.dropdown, enabled=enabled)

class DpgSettingParamBool(DpgSettingParamField):

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.checkbox = None

    def create_gui(self):
        self.checkbox = dpg.add_checkbox(callback=self._dpg_callback)

    def set_value(self, value):
        dpg.set_value(self.checkbox, bool(value))

    def get_value(self):
        return 1 if dpg.get_value(self.checkbox) else 0

    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.bind_item_theme(self.checkbox, INVALID_FIELD_THEME)
        else:
            dpg.bind_item_theme(self.checkbox, None)

    def set_enabled(self, enabled: bool):
        dpg.configure_item(self.checkbox, enabled=enabled)

class DpgSettingParamNumeric(DpgSettingParamField):
    """Shared base for numeric input fields backed by InputIntPy/InputFloatPy."""

    INPUT_CLASS: type[InputNumericPy] = None  # override in subclass
    CAST = None         # override in subclass

    def __init__(self, descriptor: ThreespaceSettingParamDescriptor):
        super().__init__(descriptor)
        self.input = None

    def create_gui(self):
        DEFAULT_WIDTH = 100
        self.input = self.INPUT_CLASS(width=DEFAULT_WIDTH, callback=self._generic_callback)
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

    def set_enabled(self, enabled: bool):
        dpg.configure_item(self.input.field, enabled=enabled)

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
        self.input = dpg.add_input_text(width=200, callback=self._dpg_callback)
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

    def set_enabled(self, enabled: bool):
        dpg.configure_item(self.input, enabled=enabled)

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

@dataclass
class SectionData:
    """Data stored per section in DpgSettingMenu."""
    settings: list["DpgSetting"] = field(default_factory=list)
    all_valid: bool = True
    dirty: bool = False

class DpgSettingMenu:
    """
    A data-only settings menu that organises DpgSetting objects into named sections.

    Usage
    -----
    - Call ``add_section(name)`` up-front to register sections in a desired order.
    - Call ``add_setting(setting, category)`` to place a setting into a section.
      If *category* is omitted the setting goes into ``"Unspecified"``.
    - The special ``stream_slots`` / ``log_slots`` settings automatically have their
      ``valid_values`` patched with live sensor options when ``sensor`` is supplied.

    This class intentionally has no GUI code; see ``DpgSettingMenuGui`` for that.
    """

    _DEFAULT_CATEGORY = "Unspecified"

    def __init__(self, sensor: ThreespaceSensor):
        self.sensor = sensor

        self.sections: dict[str, SectionData] = {}
        self.documentation = SettingsDocumentationTable()

    # ------------------------------------------------------------------
    # Section management
    # ------------------------------------------------------------------

    def add_section(self, name: str):
        """Register a section.  If it already exists this is a no-op."""
        if name in self.sections:
            return
        self.sections[name] = SectionData()

    @property
    def settings(self) -> "list[DpgSetting]":
        """Flat view of every setting across all sections, in insertion order."""
        return [s for section in self.sections.values() for s in section.settings]

    # ------------------------------------------------------------------
    # Adding settings
    # ------------------------------------------------------------------

    def add_setting(self, setting: "DpgSetting", category: str | None = None):
        """Add a pre-built DpgSetting to the menu under *category*.

        If *category* is ``None`` the setting goes into ``"Unspecified"``.
        If the section does not yet exist it is created on demand.
        """
        if category is None:
            category = self._DEFAULT_CATEGORY
        if category not in self.sections:
            self.add_section(category)

        # Patch stream/log slot valid_values with live sensor data.
        if setting.descriptor.key in ("stream_slots", "log_slots"):
            valid_params = data_charts.get_all_options_from_sensor(self.sensor)
            setting.descriptor.param_descriptors[0].valid_values = valid_params

        self.sections[category].settings.append(setting)
        setting.on_change.subscribe(self._on_setting_changed)

    # ------------------------------------------------------------------
    # Section state queries
    # ------------------------------------------------------------------

    def is_section_dirty(self, section_name: str) -> bool:
        """Return True if any setting in *section_name* has an unapplied change."""
        if section_name not in self.sections:
            return False
        return self.sections[section_name].dirty

    def is_section_valid(self, section_name: str) -> bool:
        """Return True if all settings in *section_name* are currently valid."""
        if section_name not in self.sections:
            return True
        return self.sections[section_name].all_valid

    def set_section_invalid(self, section_name: str, is_invalid: bool):
        if section_name not in self.sections:
            return
        self.sections[section_name].all_valid = not is_invalid
        self._on_section_state_changed(section_name)

    # ------------------------------------------------------------------
    # Internal change handler
    # ------------------------------------------------------------------

    def _on_section_state_changed(self, section_name: str):
        """Called whenever a section's validity or dirty state may have changed.
        Subclasses can override to react (e.g. update themes)."""
        pass

    def _find_setting(self, key: str) -> "tuple[str, SectionData, DpgSetting] | tuple[None, None, None]":
        """Return (section_name, section, setting) for the given key, or (None, None, None)."""
        for section_name, section in self.sections.items():
            for setting in section.settings:
                if setting.descriptor.key == key:
                    return section_name, section, setting
        return None, None, None

    def _on_setting_changed(self, key: str, new_value: Any):
        category, section, setting = self._find_setting(key)
        if category is None:
            return

        state_changed = False

        # Validity: only rescan if this setting's validity could flip the section state
        setting_valid = setting.pre_validate()
        if not setting_valid and section.all_valid:
            # Section just became invalid
            section.all_valid = False
            state_changed = True
        elif setting_valid and not section.all_valid:
            # This setting recovered — rescan to see if section is fully valid again
            if all(s.pre_validate() for s in section.settings):
                section.all_valid = True
                state_changed = True

        # Dirty: only rescan if this setting's dirty state could flip the section state
        setting_dirty = setting.is_dirty()
        if setting_dirty and not section.dirty:
            # Section just became dirty
            section.dirty = True
            state_changed = True
        elif not setting_dirty and section.dirty:
            # This setting cleaned up — rescan to see if section is fully clean
            if not any(s.is_dirty() for s in section.settings):
                section.dirty = False
                state_changed = True

        if state_changed:
            self._on_section_state_changed(category)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def validate_all(self) -> bool:
        """Validate every setting and update section validity flags."""
        all_valid = True
        for name, section in self.sections.items():
            section.all_valid = True
            for setting in section.settings:
                valid = setting.pre_validate()
                if not valid:
                    print(f"Invalid setting: {setting.descriptor.key} in section {name}")
                section.all_valid = section.all_valid and valid
                all_valid = all_valid and valid
            self._on_section_state_changed(name)
        print("All Valid:", all_valid)
        return all_valid

    def cache_all_values(self):
        """Snapshot the current UI values as the cached baseline for all settings."""
        for setting in self.settings:
            setting.cache_value()
        for name, section in self.sections.items():
            section.dirty = False
            self._on_section_state_changed(name)

    def apply_all(self, dirty_only: bool = True) -> bool:
        """Write all (or only dirty) settings to the sensor."""
        all_success = True
        for name, section in self.sections.items():
            section.all_valid = True
            for setting in section.settings:
                if dirty_only and not setting.is_dirty():
                    continue
                success = setting.apply(self.sensor)
                if not success:
                    print(f"Failed to apply setting: {setting.descriptor.key} in section {name}")
                all_success = all_success and success
                section.all_valid = section.all_valid and success
            if section.all_valid:
                section.dirty = False
            self._on_section_state_changed(name)
        return all_success

    def set_setting_enabled(self, key: str, enabled: bool = True):
        """Enable or disable the input fields for the setting with the given key."""
        setting = next((s for s in self.settings if s.descriptor.key == key), None)
        if setting is not None:
            setting.set_enabled(enabled)

    def reload_values(self):
        """Re-read all writable settings from the sensor and update the UI values."""
        writeable_settings = self.sensor.readAllWritableSettings()
        for setting in self.settings:
            key = setting.descriptor.key
            if key in writeable_settings:
                setting.set_value(writeable_settings[key])
        self.cache_all_values()
        self.validate_all()


@dataclass
class SectionDataGui(SectionData):
    """Extends SectionData with DearPyGui widget IDs for DpgSettingMenuGui.

    ``gui`` maps the fixed keys ``"header"``, ``"primary"``, ``"secondary"``
    (and any dynamic subsection keys) to DPG item IDs (int) or None before
    the widgets are created.
    """
    gui: dict[str, int | None] = field(
        default_factory=lambda: {"header": None, "primary": None, "secondary": None}
    )


class DpgSettingMenuGui(DpgSettingMenu):
    """
    A DpgSettingMenu that also owns the DearPyGui widgets for each section.

    Default section order matches the TSS-3 documentation layout.  Call
    ``add_section`` before adding settings to guarantee a specific ordering;
    any section that does not yet exist when a setting is added will be
    appended automatically.

    Call ``create_gui()`` once (after all settings have been added) to
    materialise the collapsing-header hierarchy.
    """

    DEFAULT_SECTION_ORDER = [
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

    def __init__(self, sensor: ThreespaceSensor):
        super().__init__(sensor)
        self.sections: dict[str, SectionDataGui]  # narrow the base annotation
        # Pre-register sections in the desired display order.
        for section in self.DEFAULT_SECTION_ORDER:
            self.add_section(section)

    # ------------------------------------------------------------------
    # Section management (extends base to add GUI slot)
    # ------------------------------------------------------------------

    def add_section(self, name: str):
        if name in self.sections:
            return
        self.sections[name] = SectionDataGui()

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------

    def _update_all_section_themes(self):
        for section in self.sections:
            self._update_section_theme(section)

    def _update_section_theme(self, section_name: str):
        if section_name not in self.sections:
            return
        section = self.sections[section_name]
        if section.gui.get("header") is None:
            return  # GUI not yet created
        is_invalid = not section.all_valid
        dirty = section.dirty
        if is_invalid:
            dpg.bind_item_theme(section.gui["header"], INVALID_SECTION_THEME)
            dpg.bind_item_theme(section.gui["primary"], _RESET_THEME)
            dpg.bind_item_theme(section.gui["secondary"], _RESET_THEME)
        elif dirty:
            dpg.bind_item_theme(section.gui["header"], CACHED_VALUE_SECTION_THEME)
            dpg.bind_item_theme(section.gui["primary"], _RESET_THEME)
            dpg.bind_item_theme(section.gui["secondary"], _RESET_THEME)
        else:
            dpg.bind_item_theme(section.gui["header"], None)
            dpg.bind_item_theme(section.gui["primary"], None)
            dpg.bind_item_theme(section.gui["secondary"], None)

    def _on_section_state_changed(self, section_name: str):
        """Update the section's theme whenever its validity or dirty state changes."""
        self._update_section_theme(section_name)

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------

    def create_gui(self):
        for section_name, section in self.sections.items():
            header = dpg.add_collapsing_header(label=section_name, default_open=False, show=False)
            primary = dpg.add_group(parent=header)
            secondary = dpg.add_group(parent=header)
            section.gui["header"] = header
            section.gui["primary"] = primary
            section.gui["secondary"] = secondary
            self._update_section_theme(section_name)

            for setting in section.settings:
                subsection = "primary"
                try:
                    documentation = self.documentation[setting.descriptor.key]
                    if "%d" in documentation["key"]:
                        subsection = get_subkey(documentation["key"], setting.descriptor.key) or "primary"
                        if subsection not in section.gui:
                            section.gui[subsection] = dpg.add_tree_node(
                                label=subsection, parent=secondary, default_open=False
                            )
                except KeyError:
                    pass
                dpg.show_item(section.gui["header"])
                dpg.push_container_stack(section.gui[subsection])
                setting.create_gui()
                dpg.pop_container_stack()
        self.cache_all_values()

    # ------------------------------------------------------------------
    # Convenience: build hierarchy from sensor (mirrors old create_hierarchy)
    # ------------------------------------------------------------------

    def create_hierarchy(self):
        """Read all writable settings from the sensor and populate the menu."""
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

            setting = DpgSetting.create(desc)
            setting.set_value(value)
            setting.set_description(description)
            self.add_setting(setting, category)

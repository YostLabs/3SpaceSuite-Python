import gui.setting_gui.setting_structures as setting_structures
from gui.setting_gui.setting_structures import ThreespaceSettingDescriptor, DpgSetting, register_setting
from dpg_ext.input_fields import DraggableList
import dearpygui.dearpygui as dpg
from yostlabs.tss3 import StreamableCommands
from utility import Logger

@register_setting(r"^calib_mat_\w+\d+$")
class MatrixSetting(DpgSetting):
    """Displays a 9-parameter setting as a 3x3 grid of inputs instead of a flat row."""

    COLS = 3

    INDENT = 24

    def create_gui(self):
        with dpg.group(horizontal=True):
            self._key_label = dpg.add_text(self.descriptor.key)
            self._add_help_tag()
        with dpg.group(indent=self.INDENT):
            for row in range(3):
                with dpg.group(horizontal=True):
                    for col in range(self.COLS):
                        self.params[row * self.COLS + col].create_gui()
        self._ui_initialized = True
        if self._tmp_value is not None:
            self.set_value(self._tmp_value)
            self._tmp_value = None

@register_setting(r"^calib_bias_\w+\d+$")
class VectorSetting(DpgSetting):
    """Displays all parameters on a single indented line below the key label."""

    INDENT = 24

    def create_gui(self):
        with dpg.group(horizontal=True):
            self._key_label = dpg.add_text(self.descriptor.key)
            self._add_help_tag()
        with dpg.group(horizontal=True, indent=self.INDENT):
            for param in self.params:
                param.create_gui()
        self._ui_initialized = True
        if self._tmp_value is not None:
            self.set_value(self._tmp_value)
            self._tmp_value = None

class OrderedItemSelection(DpgSetting):
    """Drag-and-drop ordered selection for primary sensor priority settings.

    Left panel ("Priority Order") — active ordered selection.
    Right panel ("Available")     — unused options.

    Items can be dragged freely between the two panels and reordered within
    the active panel.  Implemented using two linked DraggableList instances.

    If pin_items are supplied, these items will be permanently available in the active list and
    not movable. The set is a dictionary of keys to values. If the value is None, it will attempt
    to grab the value from the key map of the descriptors valid values for this setting.
    """

    MIN_ITEM_WIDTH = 100

    def __init__(self, descriptor: ThreespaceSettingDescriptor, orderable=True, order_by="label",
                 active_label="Active", inactive_label="Available", pin_items: dict[str, any] = None):
        super().__init__(descriptor)
        self._item_map = self.params[0].descriptor.valid_values  # {label: value}
        self._value_to_key_map = { v: k for k, v in self._item_map.items() }

        self._active_label = active_label
        self._inactive_label = inactive_label

        self._pinned_items = pin_items
        if self._pinned_items is not None:
            for key, value in self._pinned_items.items():
                if value is None:
                    self._pinned_items[key] = self._item_map.get(key)

        self._active_list: DraggableList | None = None
        self._available_list: DraggableList | None = None
        self._orderable = orderable
        self._order_by = order_by

        self._item_width = max(self.MIN_ITEM_WIDTH, max((dpg.get_text_size(label)[0] for label in self._item_map), default=0) + 8)
        self._list_height = len(self._item_map) * DraggableList.ITEM_HEIGHT + DraggableList.PANEL_PADDING
        self._payload_type = f"ois_{descriptor.key}"

    def create_gui(self):
        with dpg.group(horizontal=True):
            self._key_label = dpg.add_text(self.descriptor.key)
            self._add_help_tag()
        with dpg.group(horizontal=True, indent=24):
            with dpg.group():
                dpg.add_text(self._active_label, color=(180, 180, 180))
                self._active_list = DraggableList(
                    payload_type=self._payload_type,
                    width=self._item_width + 16,
                    height=self._list_height,
                    item_width=self._item_width,
                    reorderable=self._orderable,
                    order_by=self._order_by
                )
                self._active_list.on_change.subscribe(lambda v: self._on_param_changed(None, v))
                if self._pinned_items is not None:
                    self._active_list.pin_items([( key, value ) for key, value in self._pinned_items.items()])
            dpg.add_text(" <-> ")
            with dpg.group():
                dpg.add_text(self._inactive_label, color=(180, 180, 180))
                self._available_list = DraggableList(
                    payload_type=self._payload_type,
                    width=self._item_width + 16,
                    height=self._list_height,
                    item_width=self._item_width,
                    reorderable=False,
                    order_by=self._order_by
                )

        if not self._ui_initialized:
            self._ui_initialized = True
            # Start with what has already been set, or default to everything in available
            value = self._tmp_value or []
            self.set_value(value)
            self._tmp_value = None

    def get_value(self):
        return ",".join(str(value) for _label, value in self._active_list.get_items())

    def set_value(self, value):
        if not self._ui_initialized:
            self._tmp_value = value
            return
        
        #Convert to values based on type
        if isinstance(value, (list, tuple)):
            active_values = [int(v) for v in value]
        elif isinstance(value, str):
            active_values = [int(v) for v in value.split(",") if v.strip()] if value.strip() else []
        else:
            active_values = []

        #Trim the set to only the valid values
        valid_set = set(self._item_map.values())
        active_values = [v for v in active_values if v in valid_set]

        #Build the list of tuples (key, value) for the active set and inactive set
        active_items = []
        for value in active_values:
            key = self._value_to_key_map[value]
            active_items.append((key, value))
        
        available_items = []
        for label, value in self._item_map.items():
            if value not in active_values and label not in self._pinned_items:
                available_items.append((label, value))

        #Update the lists with the correct items
        self._active_list.set_items(active_items)
        self._available_list.set_items(available_items)

    def pre_validate(self):
        value = self.get_value()
        valid = self.params[0].descriptor.validate(value)
        self.mark_invalid(not valid)
        return valid

    def mark_invalid(self, is_invalid: bool):
        if self._active_list is not None:
            dpg.bind_item_theme(self._active_list.window, setting_structures.INVALID_FIELD_THEME if is_invalid else None)
            button_theme = setting_structures._RESET_THEME if is_invalid else None
            self._active_list.set_button_theme(button_theme)
            self._available_list.set_button_theme(button_theme)

@register_setting(r"^primary_(accel|gyro|mag)$")
class PrimaryComponentSelection(OrderedItemSelection):
    """Special case of OrderedItemSelection for primary component selection settings, with a different default order and labels."""

    def __init__(self, descriptor):
        super().__init__(descriptor, active_label="Priority Order")

@register_setting(r"^log_(start|stop)_event$")
class LogEventSelection(OrderedItemSelection):
    """Same as OrderedItemSelection but with specific configuration"""

    def __init__(self, descriptor):
        super().__init__(descriptor, orderable=False, order_by="value", 
                         active_label="Enabled", inactive_label="Disabled", pin_items={"Command": None})

@register_setting(r"^led_rgb$")
class ColorSetting(DpgSetting):
    def __init__(self, descriptor, description=None, default_value=(0, 0, 255)):
        super().__init__(descriptor)
        self.cached_value = default_value
        self.color_picker = None
        self.description = description

    def create_gui(self):
        with dpg.group(horizontal=True):
            self._key_label = dpg.add_text(self.descriptor.key)
            self.color_picker = dpg.add_color_edit(
                label="", default_value=self.cached_value, 
                no_alpha=True, display_type=dpg.mvColorEdit_float,
                width=200, callback=lambda: self._on_param_changed(None, self.get_value()))
            if self.description:
                help_tag = dpg.add_text(" ?", color=(120, 170, 255))
                with dpg.tooltip(parent=help_tag):
                    dpg.add_text(self.description, wrap=700)

    def get_value(self):
        """
        Gets RGB value as a list with range 0-1
        """
        value = None
        if self.color_picker is None:
            value = self.cached_value
        else:
            value = dpg.get_value(self.color_picker)
        value = [v / 255 for v in value[:3]]  # Convert from 0-255 range to 0-1 range, ignore alpha
        value = [max(0, min(1, v)) for v in value]  # Clamp values to 0-1   
        return value
    
    def set_value(self, rgb: list):
        """
        Set value using RGB with range 0-1
        """
        rgb = [255 * v for v in rgb] # Convert from 0-1 range to 0-255
        self.cached_value = [*rgb, 255]  # Ensure alpha is always 255
        if self.color_picker is not None:
            dpg.set_value(self.color_picker, self.cached_value)

    def pre_validate(self):
        value = self.get_value()
        all_valid = True
        for i, param in enumerate(self.params):
            valid = param.descriptor.validate(value[i])
            all_valid = all_valid and valid
        self.mark_invalid(not all_valid)
        return all_valid

    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.bind_item_theme(self.color_picker, setting_structures.INVALID_FIELD_THEME)
        else:
            dpg.bind_item_theme(self.color_picker, None)

from gui.streaming_menu import StreamingOptionSelectionMenu, ThreespaceStreamingOption

@register_setting(r"^(stream|log)_slots$")
class StreamingSelection(DpgSetting):

    def __init__(self, descriptor: ThreespaceSettingDescriptor):
        super().__init__(descriptor)
        self.selection_menu: StreamingOptionSelectionMenu = None

    def create_gui(self):
        with dpg.group(horizontal=True):
            self._key_label = dpg.add_text(self.descriptor.key)
            self._add_help_tag()
            self.failure_text = dpg.add_text("Failed to apply.", color=setting_structures.INVALID_COLOR, show=False)
        self.selection_menu = StreamingOptionSelectionMenu(valid_options=self.params[0].descriptor.valid_values, 
                                                           on_modified_callback=self.on_value_changed)

        #Load initial value
        if not self._ui_initialized:
            self._ui_initialized = True
            # Start with what has already been set, or default to everything in available
            value = self._tmp_value or "255"
            self.set_value(value)
            self._tmp_value = None

    def on_value_changed(self, menu: StreamingOptionSelectionMenu):
        self._on_param_changed(None, self.get_value())

    def get_value(self):
        if self.selection_menu is None:
            return self._tmp_value or "255"
        options = self.selection_menu.get_options()
        formatted_options = []
        for option in options:
            if option.param is None:
                formatted_options.append(str(option.cmd.value))
            else:
                formatted_options.append(f"{option.cmd.value}:{option.param}")
        if len(formatted_options) == 0:
            return "255"  # Special case for empty set since an empty string is not valid for the setting
        return ','.join(formatted_options)
    
    def set_value(self, value: str):
        if not self._ui_initialized:
            self._tmp_value = value
            return
        
        value = value.strip()
        if value == "":
            value = "255"

        str_options = value.split(',')
        options: list[tuple] = []
        for s in str_options:
            cmd = s
            param = None
            if ':' in s:
                cmd, param = s.split(':')
            
            #None option
            if cmd == "255":
                continue

            try:
                cmd = StreamableCommands(int(cmd))
            except ValueError:
                raise ValueError(f"Invalid command value: {cmd}")

            if param is not None:
                try:
                    param = int(param)
                except ValueError:
                    raise ValueError(f"Invalid parameter value: {param}")
            
            options.append(ThreespaceStreamingOption(cmd, param))

        #Nothing selected, use the special "none" value
        if len(options) == 0:
            options.append(ThreespaceStreamingOption(None, None))

        self.selection_menu.overwrite_options(options)
    
    def pre_validate(self):
        value = self.get_value()
        valid = self.params[0].descriptor.validate(value)
        self.mark_invalid(not valid)
        return valid
    
    def mark_invalid(self, is_invalid):
        if is_invalid:
            dpg.show_item(self.failure_text)
        else:
            dpg.hide_item(self.failure_text)
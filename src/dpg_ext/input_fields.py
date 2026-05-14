import dearpygui.dearpygui as dpg
from utility import Callback
import itertools


class InputNumericPy:
    """
    Base class for numeric text input fields backed by dpg.add_input_text.
    Validates on deactivation and reverts to last valid value if input is invalid.
    Subclasses must define CAST (e.g. int or float).
    """

    CAST = None  # override in subclass
    VALIDATION_HANDLER_REGISTRY = None
    DEACTIVATED_AFTER_EDIT_HANDLER = None

    def __init__(
        self,
        label: str = "",
        default_value=0,
        min_value=None,
        max_value=None,
        width: int = -1,
        callback=None,
        tag: str | int = 0,
        parent: str | int = 0,
        **kwargs
    ):
        self.min_value = min_value
        self.max_value = max_value
        self.callback = callback
        self._last_valid = self.CAST(default_value)

        optional = {}
        if tag:
            optional["tag"] = tag
        if parent:
            optional["parent"] = parent

        # Use DPG's built-in decimal flag by default so invalid characters are
        # blocked at the ImGui level (works while the field is focused, unlike
        # set_value inside a callback). Subclasses may override via kwargs.
        kwargs.setdefault('decimal', True)

        self._field = dpg.add_input_text(
            label=label,
            default_value=str(self._last_valid),
            width=width,
            user_data=self,
            **optional,
            **kwargs,
        )

        cls = type(self)
        if cls.VALIDATION_HANDLER_REGISTRY is None:
            cls.VALIDATION_HANDLER_REGISTRY = dpg.add_item_handler_registry()
            cls.DEACTIVATED_AFTER_EDIT_HANDLER = dpg.add_item_deactivated_after_edit_handler(
                parent=cls.VALIDATION_HANDLER_REGISTRY,
                callback=cls._on_deactivated,
            )

        dpg.bind_item_handler_registry(self._field, cls.VALIDATION_HANDLER_REGISTRY)

    @property
    def field(self) -> int:
        """The DPG item id of the underlying input_text widget."""
        return self._field

    def get_value(self):
        """Get the current validated value."""
        return self._last_valid

    def set_value(self, new_value):
        """Set the value programmatically, applying clamping."""
        new_value = self._clamp(self.CAST(new_value))
        self._last_valid = new_value
        dpg.set_value(self._field, str(new_value))

    def set_range(self, min_value=None, max_value=None):
        """Set the valid range. The current value will be clamped to the new range."""
        self.min_value = min_value
        self.max_value = max_value
        self.set_value(self._last_valid)

    def get_required_width_by_current_range(self, char_width=8, padding=16):
        """Return the widget width based on the maximum number of characters in the valid range.
        Returns None if either min_value or max_value is None."""
        if self.min_value is None or self.max_value is None:
            return None
        max_chars = max(len(str(self.min_value)), len(str(self.max_value)))
        return max_chars * char_width + padding

    def set_width(self, width: int):
        """Set the width of the input field."""
        dpg.configure_item(self._field, width=width)

    def _clamp(self, value):
        if self.min_value is not None and value < self.min_value:
            value = self.min_value
        if self.max_value is not None and value > self.max_value:
            value = self.max_value
        return value

    @staticmethod
    def _on_deactivated(handler, sender, user_data):
        instance: InputNumericPy = dpg.get_item_user_data(sender)
        raw = dpg.get_value(sender)
        try:
            parsed = instance._clamp(instance.CAST(raw))
            instance._last_valid = parsed
            dpg.set_value(sender, str(parsed))
        except (ValueError, TypeError):
            dpg.set_value(sender, str(instance._last_valid))
            return

        if instance.callback:
            instance.callback(instance._field, instance._last_valid, instance)


class InputIntPy(InputNumericPy):
    """Emulates dpg.add_input_int() using add_input_text, supporting arbitrary Python int sizes.
    Optionally displays values in hex (e.g. 0x1F). When hex mode is enabled, the user may
    enter values in either decimal or hex (0x-prefixed).
    """
    CAST = int

    def __init__(self, *args, hex_display: bool = False, **kwargs):
        self.hex_display = hex_display
        if hex_display:
            # DPG's hexadecimal flag omits 'x', preventing '0x' prefixes, so
            # hex mode relies on deactivation-only validation instead.
            kwargs['decimal'] = False
        super().__init__(*args, **kwargs)
        # Re-display default value in hex if needed (super().__init__ used str())
        if hex_display:
            dpg.set_value(self._field, self._to_display(self._last_valid))

    def set_display_mode(self, mode: str):
        if mode == "hex":
            self.hex_display = True
            dpg.set_value(self._field, self._to_display(self._last_valid))
            dpg.configure_item(self._field, decimal=False)
        else:
            self.hex_display = False
            dpg.set_value(self._field, str(self._last_valid))
            dpg.configure_item(self._field, decimal=True)

    def _to_display(self, value: int) -> str:
        """Format an integer for display."""
        if self.hex_display:
            return hex(value)  # e.g. '0x1f'
        return str(value)

    def set_value(self, new_value):
        new_value = self._clamp(int(new_value))
        self._last_valid = new_value
        dpg.set_value(self._field, self._to_display(new_value))

    def get_required_width_by_current_range(self, char_width=8, padding=16):
        """Return widget width based on the widest possible display string in the valid range.
        Returns None if either min_value or max_value is None."""
        if self.min_value is None or self.max_value is None:
            return None
        if self.hex_display:
            max_chars = max(len(hex(self.min_value)), len(hex(self.max_value)))
        else:
            max_chars = max(len(str(self.min_value)), len(str(self.max_value)))
        return max_chars * char_width + padding

    @staticmethod
    def _on_deactivated(handler, sender, user_data):
        instance: InputIntPy = dpg.get_item_user_data(sender)
        raw = dpg.get_value(sender).strip()
        try:
            # Accept both '0x1f' hex and plain decimal
            parsed = instance._clamp(int(raw, 0) if instance.hex_display else int(raw))
            instance._last_valid = parsed
            dpg.set_value(sender, instance._to_display(parsed))
        except (ValueError, TypeError):
            dpg.set_value(sender, instance._to_display(instance._last_valid))
            return

        if instance.callback:
            instance.callback(instance._field, instance._last_valid, instance)


class InputFloatPy(InputNumericPy):
    """Emulates dpg.add_input_float() using add_input_text, supporting arbitrary Python float precision.
    Displays values rounded to 6 decimal places.
    """
    CAST = float
    DECIMAL_PLACES = 6

    def _to_display(self, value: float) -> str:
        return f"{value:.{self.DECIMAL_PLACES}f}"

    def set_value(self, new_value):
        new_value = self._clamp(float(new_value))
        self._last_valid = new_value
        dpg.set_value(self._field, self._to_display(new_value))

    @staticmethod
    def _on_deactivated(handler, sender, user_data):
        instance: InputFloatPy = dpg.get_item_user_data(sender)
        raw = dpg.get_value(sender)
        try:
            parsed = instance._clamp(float(raw))
            instance._last_valid = parsed
            dpg.set_value(sender, instance._to_display(parsed))
        except (ValueError, TypeError):
            dpg.set_value(sender, instance._to_display(instance._last_valid))
            return

        if instance.callback:
            instance.callback(instance._field, instance._last_valid, instance)


class DraggableList:
    """A child-window containing an ordered list of labelled items that can be
    reordered internally via drag-and-drop, and transferred to any other
    DraggableList that shares the same payload_type.

    Each item is a (label: str, value: any) pair.  The label is shown on the
    button; the value is opaque data retrievable via get_items().

    No explicit linking is required — sharing a payload_type is sufficient for
    cross-list transfers.  Items are tracked by a monotonic integer ID so that
    stale indices from a previous rebuild can never cause incorrect behaviour.

    If reorderable=False, items cannot be reordered by dragging onto other items
    within this list, and items are always kept in ascending label order.
    """

    ITEM_HEIGHT = 28   # px per button row (tune to match your DPG theme)
    PANEL_PADDING = 12  # extra px for the child_window border

    _id_counter = itertools.count()

    def __init__(
        self,
        payload_type: str,
        width: int = 120,
        height: int = -1,
        item_width: int = -1,
        parent: int | str = 0,
        reorderable: bool = True,
    ):
        self._payload_type = payload_type
        self._item_width = item_width if item_width != -1 else width - 16
        self._reorderable = reorderable
        self._button_theme = None
        # Each entry: {"id": int, "label": str, "value": any}
        self._items: list[dict] = []

        self.on_change = Callback()

        kwargs = {}
        if parent:
            kwargs["parent"] = parent

        self._window = dpg.add_child_window(
            width=width,
            height=height,
            border=True,
            drop_callback=self._on_drop_panel,
            payload_type=self._payload_type,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def window(self) -> int:
        """The underlying DPG child_window item id."""
        return self._window

    @property
    def reorderable(self) -> bool:
        """Whether items can be reordered by dragging within this list."""
        return self._reorderable

    @reorderable.setter
    def reorderable(self, value: bool):
        self._reorderable = value
        if not value:
            self._sort()
        self._rebuild()

    def get_items(self) -> list[tuple]:
        """Return a copy of the current items as (label, value) tuples, in order."""
        return [(item["label"], item["value"]) for item in self._items]

    def set_items(self, items: list[tuple]):
        """Replace all items. Each element should be (label, value)."""
        self._items = [{"id": next(self._id_counter), "label": lbl, "value": val}
                       for lbl, val in items]
        if not self._reorderable:
            self._sort()
        self._rebuild()

    def add_items(self, items: list[tuple]):
        """Append items to the end of the list."""
        for lbl, val in items:
            self._items.append({"id": next(self._id_counter), "label": lbl, "value": val})
        if not self._reorderable:
            self._sort()
        self._rebuild()

    def clear(self):
        self._items.clear()
        self._rebuild()

    def set_button_theme(self, theme):
        """Set a DPG theme to apply to every button in this list.
        Pass None to remove any previously set theme."""
        self._button_theme = theme
        self._rebuild()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sort(self):
        """Sort items alphabetically by label in-place."""
        self._items.sort(key=lambda item: item["label"])

    def _rebuild(self):
        dpg.delete_item(self._window, children_only=True)
        for item in self._items:
            # Only register item-level drop targets when reorderable
            drop_cb = self._on_drop_item if self._reorderable else None
            pt = self._payload_type if self._reorderable else None
            btn = dpg.add_button(
                label=f"  {item['label']}  ",
                width=self._item_width,
                parent=self._window,
                drop_callback=drop_cb,
                payload_type=pt,
                user_data=item["id"],
            )
            with dpg.drag_payload(
                parent=btn,
                drag_data=(self, item["id"]),
                payload_type=self._payload_type,
            ) as payload:
                dpg.add_text(item["label"])

            if self._button_theme is not None:
                dpg.bind_item_theme(btn, self._button_theme)
                dpg.bind_item_theme(payload, self._button_theme)

    def _take_by_id(self, item_id: int) -> dict:
        """Remove and return the item with the given id."""
        for i, item in enumerate(self._items):
            if item["id"] == item_id:
                item = self._items.pop(i)
                self.on_change._notify(self.get_items())
                return item
        raise KeyError(f"DraggableList: no item with id {item_id}")

    def _insert_item(self, item: dict, before_id: int | None = None):
        """Insert item before the item with before_id, or append if None."""
        if before_id is None:
            self._items.append(item)
        else:
            for i, existing in enumerate(self._items):
                if existing["id"] == before_id:
                    self._items.insert(i, item)
                    self.on_change._notify(self.get_items())
                    return
            self._items.append(item)  # fallback: target gone, append

    # ------------------------------------------------------------------
    # Drop callbacks
    # ------------------------------------------------------------------

    def _on_drop_item(self, sender, app_data, user_data):
        """Dropped onto a specific item — insert before it."""
        #The list the item being dragged is from, and the ID of the dragged item
        source_list, source_id = app_data
        source_list: DraggableList
        source_id: int

        #The item the dragged item was dropped on
        target_id = dpg.get_item_user_data(sender)

        #Item dropped onto itself, do nothing
        if source_id == target_id:
            return

        #Remove item from whatever list it came from
        item = source_list._take_by_id(source_id)
        if source_list is not self:
            #If item from another list, re-render that list
            source_list._rebuild()

        #Put item into the list of the item it was dropped on (AKA the owner of the callback function which is self)
        self._insert_item(item, before_id=target_id)
        self._rebuild()

    def _on_drop_panel(self, sender, app_data, user_data):
        """Dropped onto the panel background — append to end."""
        #The list the item being dragged is from, and the ID of the dragged item
        source_list, source_id = app_data
        source_list: DraggableList
        source_id: int

        #Remove item from list it is being taken from/moved in
        item = source_list._take_by_id(source_id)

        #If removing from another list, re-render the other list
        if source_list is not self:
            source_list._rebuild()

        #Put item at end of the list it was dropped on and re-render
        self._items.append(item)
        self.on_change._notify(self.get_items())
        if not self._reorderable:
            self._sort()
        self._rebuild()



if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport()

    with dpg.window() as primary_window:
        field = InputIntPy(label="Integer Input", default_value=5, min_value=-100, max_value=100, width=200)
        float_field = InputFloatPy(label="Float Input", default_value=3.14, min_value=0.0, max_value=10.0, width=200)


    dpg.set_primary_window(primary_window, True)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
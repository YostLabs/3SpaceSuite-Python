import dearpygui.dearpygui as dpg
from dpg_ext.extension_functions import *
from dpg_ext.staged_view import StagedView
from dpg_ext.global_lock import dpg_lock

class FilteredDropdown(StagedView):

    def __init__(self, items = None, default_item=None, callback=None, allow_custom_options=True, allow_empty=True, hint = "", width=300, window_height=300, **dropdown_args):
        """
        Params
        ------
        allow_custom_options : If set to true, then it will act more like an input_text field, such that the callback will also trigger every time a character is entered. And if enter is pressed, the current value of the field will be added to the dropdown list
        allow_empty : If true, allows for an unselected option when entering in no value
        """
        self.allow_custom = allow_custom_options
        self.allow_empty = allow_empty

        self.dropdown_window = None
        self.cur_selection_name = None
        self.selected_selectable = None

        self.callback = callback
        self.window_height = window_height

        self.modifiable = True

        with dpg.stage(label="Filtered Dropdown Input Stage") as self._stage_id:
            self.dropdown_input = dpg.add_input_text(hint=hint, callback=self.__on_enter_pressed, on_enter=True, width=width, auto_select_all=True, **dropdown_args)
        with dpg.item_handler_registry(label="FilteredDropdownInputHandler") as self.dropdown_registry:
            dpg.add_item_activated_handler(callback=self.__on_activated)
            dpg.add_item_deactivated_handler(callback=self.__on_input_text_deactivated)
            dpg.add_item_edited_handler(callback=self.__on_text_changed)
            dpg.add_item_resize_handler(callback=self.__on_resize)
        dpg.bind_item_handler_registry(self.dropdown_input, self.dropdown_registry)

        self.selectables: dict[str,int] = {} #Label -> Selectable

        if items is None:
            items = []

        #Setup the actual dropdown that will be used
        with dpg.stage(label="Filtered Dropdown Dropdown Stage") as self.dropdown_stage:
            with dpg.filter_set() as self.filter_set:
                for item in items:
                    self.add_item(item)

        if default_item is not None:
            if default_item not in self.selectables:
                self.add_item(default_item)
            self.__set_selected(self.selectables[default_item])
            dpg.set_value(self.dropdown_input, default_item)

        self.cur_selection_name = dpg.get_value(self.dropdown_input)

        #Actual dropdown needs to know when it should close if it has the focus
        with dpg.item_handler_registry(label="FilteredDropdownWindowHandler") as self.dropdown_popup_registry:
            dpg.add_item_visible_handler(callback=self.__dropdown_focus_monitor)

    def modification_enabled(self, enabled):
        self.modifiable = enabled
        dpg.configure_item(self.dropdown_input, readonly=not enabled)

    def add_item(self, item):
        if item not in self.selectables:
            s = dpg.add_selectable(label=item, filter_key=item, callback=self.__on_item_selected, parent=self.filter_set)
            self.selectables[item] = s

    def remove_item(self, item):
        if item in self.selectables:
            selectable = self.selectables.pop(item)
            dpg.delete_item(selectable)

    def clear_all_items(self):
        for selectable in self.selectables.values():
            dpg.delete_item(selectable)
        self.selectables.clear()

    def get_value(self):
        if self.allow_custom:
            return dpg.get_value(self.dropdown_input)
        return self.cur_selection_name

    def set_value(self, value: str):
        exists = value in self.selectables
        if not exists:
            if not self.allow_custom:
                return
            self.add_item(value)
        self.__set_selected(self.selectables[value])
        

    def __set_selected(self, selected_selectable):
        with dpg_lock():
            for key, selectable in self.selectables.items():
                if selectable is not selected_selectable:
                    dpg.set_value(selectable, False)
                else:
                    dpg.set_value(selectable, True)
                    self.cur_selection_name = key
                    dpg.set_value(self.dropdown_input, self.cur_selection_name)
            self.selected_selectable = selected_selectable

    def __on_text_changed(self, sender, app_data):
        with dpg_lock():
            new_value: str = dpg.get_value(app_data)
            dpg.set_value(self.filter_set, new_value)
        if self.callback is not None and self.allow_custom:
            self.callback(self.dropdown_input, new_value)

    def __finalize_selection(self, selection_name: str):
        if selection_name == "" and self.allow_empty:
            self.__set_selected(None)
            if not self.allow_custom and self.callback is not None:
                self.callback(self.dropdown_input, None)            
            return
        selection_name = [v for v in self.selectables.keys() if v.lower() == selection_name.lower()]
        if len(selection_name) == 1:
            selection_name = selection_name[0]
            self.__set_selected(self.selectables[selection_name])
            if not self.allow_custom and self.callback is not None:
                self.callback(self.dropdown_input, selection_name)
        else:
            #Go back to the previous selection
            dpg.set_value(self.dropdown_input, self.cur_selection_name)

    def __on_resize(self, sender, app_data):
        if self.dropdown_window is not None:
            with dpg_lock():
                width, height = dpg.get_item_rect_size(self.dropdown_input)

                pos = get_global_item_pos(self.dropdown_input)
                dropdown_popup_pos = (pos[0], pos[1] + height)

                dpg.configure_item(self.dropdown_window, width=width, pos=dropdown_popup_pos)

    def __on_enter_pressed(self, sender, app_data):
        """
        Pressing enter assumes it is a submission of something
        that should now be in the list
        """
        if app_data == "" and self.allow_empty:
            self.__set_selected(None)
            return
        if self.allow_custom:
            self.add_item(app_data)
        #Enter will trigger the input_text_deactivated callback, that will handle the finalize
        # self.__finalize_selection(app_data)

    def __on_item_selected(self, sender, app_data):
        with dpg_lock():
            item_value = dpg.get_item_label(sender)
        self.__deactivate_dropdown()
        self.__finalize_selection(item_value)

    def __on_activated(self, sender, app_data):
        if not self.modifiable: return
        if self.dropdown_window is None: #It could be not None if focus is returned to the input from the dropdown menu (such as scrolling)
            self.__create_dropdown()
        else:
            dpg.bind_item_handler_registry(self.dropdown_window, None)

    def __on_input_text_deactivated(self, sender, app_data):
        with dpg_lock():
            active_window = dpg.get_active_window()
            if active_window != self.dropdown_window: #Allows scrolling and actually selecting an item
                self.__deactivate_dropdown()
                self.__finalize_selection(dpg.get_value(self.dropdown_input))
            else: #The dropdown now needs to handle closing itself
                dpg.bind_item_handler_registry(self.dropdown_window, self.dropdown_popup_registry)

    def __create_dropdown(self):
        with dpg_lock():
            width, height = dpg.get_item_rect_size(self.dropdown_input)

            pos = get_global_item_pos(self.dropdown_input)
            viewport_height = dpg.get_viewport_height()

            dropdown_popup_pos_down = (pos[0], pos[1] + height)
            dropdown_popup_pos_base_up = (pos[0], pos[1] - 4)
            num_selectables = len(self.selectables)
            text_height = dpg.get_text_size("")[1]
            selectables_height = 8 * 2 + (num_selectables - 1) * 4 + num_selectables * text_height #Window_padding + (len - 1) * item_spacing + len * text_height
            #Idk why this is off by a bit less then 50, but I am just going to do -50 anyways.
            #I think it has to do with the title and menu bar, just don't care to check
            dropdown_height_down = min(self.window_height, viewport_height - dropdown_popup_pos_down[1] - 50, selectables_height)
            dropdown_height_up = min(self.window_height, selectables_height, dropdown_popup_pos_base_up[1])

            if dropdown_height_up > dropdown_height_down:
                dropdown_height = dropdown_height_up
                #The previous pos was at the base, move the pos to the top
                dropdown_popup_pos = (dropdown_popup_pos_base_up[0], dropdown_popup_pos_base_up[1] - dropdown_height)
            else:
                dropdown_height = dropdown_height_down
                dropdown_popup_pos = dropdown_popup_pos_down

            self.__set_selected(self.selected_selectable) #Make sure only the current value is selected

            with dpg.window(width=width, height=dropdown_height, min_size=[0, 0], pos=dropdown_popup_pos, no_title_bar=True, no_move=True, no_focus_on_appearing=True, no_resize=True) as self.dropdown_window:
                dpg.unstage(self.dropdown_stage)

    def __deactivate_dropdown(self):
        with dpg_lock():
            self.__remove_dropdown()
            dpg.set_value(self.filter_set, "")

    def __remove_dropdown(self):
        if self.dropdown_window is not None:
            dpg.bind_item_handler_registry(self.dropdown_window, None) #Idk if this is actually necessary, but trying
            dpg.delete_item(self.dropdown_window)
            self.dropdown_window = None

    def __dropdown_focus_monitor(self):
        """
        This function is only called when the dropdown itself has the focus
        and it is used to determine if the dropdown loses focus. It is an
        on_visible call but only happens when the dropdown itself is focused
        """
        with dpg_lock():
            if self.dropdown_window is None: #Somehow this can sometimes re enter even after the deactivate call. Not sure how, but this fixes it
                return
            
            #https://github.com/hoffstadt/DearPyGui/issues/2077, this will sometimes return false cause of a race condition bug
            #focused = dpg.is_item_focused(self.dropdown_window) or dpg.is_item_focused(self.dropdown_window)
            active = dpg.get_active_window() == self.dropdown_window or dpg.is_item_active(self.dropdown_input)
            if not active:
                self.__deactivate_dropdown()
                self.__finalize_selection(dpg.get_value(self.dropdown_input))
    
    def delete(self):
        dpg.delete_item(self.dropdown_registry)
        dpg.delete_item(self.dropdown_popup_registry)
        dpg.delete_item(self.dropdown_stage)
        super().delete()

def find_focus(item):
    state = dpg.get_item_state(item)
    if "focused" in state and state["focused"]:
        return item
    children = dpg.get_item_children(item)
    for group in children.values():
        for child in group:
            focus = find_focus(child)
            if focus is not None:
                return focus
    return None
        

#Example
if __name__=="__main__":
    dpg.create_context()
    dpg.create_viewport()
    
    with dpg.window(pos=(450, 300), width=300) as primary_window:
        with dpg.menu_bar():
            with dpg.menu(label="Tools"):
                dpg.add_menu_item(label="Registry", callback=dpg.show_item_registry)
        with dpg.tab_bar():
            with dpg.tab(label="Test Tab"):
                with dpg.group(horizontal=True) as h_group:
                    dropdown = FilteredDropdown(items=['a', 'b', 'c', 'a1', 'b1', 'c1'])
                    dropdown.submit()
                    dpg.add_text("Dropdown Label")
                random_button = dpg.add_button(label="Print Active Window", callback=lambda: print("Active Window:", dpg.get_active_window()))
            with dpg.tab(label="Test Tab 2"):
                dpg.add_text("Random Text")

    dpg.set_primary_window(primary_window, True)
    dpg.show_viewport()
    dpg.setup_dearpygui()
    dpg.start_dearpygui()
    dpg.destroy_context()
"""
Manages the macros saved/configured for the terminal as well as the
modal window for configuring/modifying macros
"""
from settings_manager import SettingsManager
import dearpygui.dearpygui as dpg
import dataclasses
from utility import Callback

@dataclasses.dataclass
class TerminalMacro:
    name: str
    text: str

class MacroManager:

    FILE_NAME = "terminal_macros.json"

    def __init__(self, settings_manager: SettingsManager):
        self.settings_manager = settings_manager

        self.on_modified = Callback()

        #Load saved macros
        self.macros: list[TerminalMacro] = self.settings_manager.load(MacroManager.FILE_NAME, object_hook=lambda d: TerminalMacro(**d))
        if self.macros is None:
            self.macros: list[TerminalMacro] = []
            self.macros.append(TerminalMacro("Valid", "?valid_components"))
            self.macros.append(TerminalMacro("Info", "?serial_number\n?version_hardware\n?version_firmware"))
            self.macros.append(TerminalMacro("ODR", "?{odr}"))
            self.macros.append(TerminalMacro("Self Test", ":128"))
            self.macros.append(TerminalMacro("Debug", ":127"))

    def add_macro(self, macro: TerminalMacro):
        if macro.name == "":
            macro.name = self.generate_unique_macro_name()
        self.macros.append(macro)

    def remove_macro(self, macro: TerminalMacro):
        """
        This is instance based, not equality based
        """
        found = False
        for i, m in enumerate(self.macros):
            if macro is m:
                found = True
                break
        if found:
            del self.macros[i]
    
    def set_macro_index(self, macro: TerminalMacro, new_index: int):
        if new_index < 0 or new_index >= len(self.macros): return
        self.remove_macro(macro)
        self.macros.insert(new_index, macro)

    def save(self):
        self.settings_manager.save(MacroManager.FILE_NAME, self.macros, default=lambda o: dataclasses.asdict(o))
    
    def generate_unique_macro_name(self):
        i = 0
        unique = False

        while not unique:
            unique = True
            name = f"M{i}"
            for macro in self.macros:
                if macro.name == name:
                    i += 1
                    unique = False
                    break
        
        return name
    
    def open_macro_config(self):
        return MacroConfigurationWindow(self)



from dpg_ext.selectable_button import SelectableButton
from core_ui import BannerMenu
class MacroConfigurationWindow:

    def __init__(self, macro_manager: MacroManager):
        with dpg.window(modal=True, no_move=False, no_resize=False, label="Macro Manager", no_close=False,
                        width=600, height=400, on_close=self.__on_close) as self.modal:
            with dpg.table(header_row=False, resizable=True):
                dpg.add_table_column(init_width_or_weight=0.3)
                dpg.add_table_column(init_width_or_weight=0.7)
                with dpg.table_row():
                    with dpg.table_cell() as self.control_cell:
                        self.search_text = dpg.add_input_text(hint="Search", width=-1, callback=lambda s, a, u: dpg.set_value(self.filter_id, a.lower()))
                        with dpg.child_window(height=-60) as self.selection_window:
                            with dpg.filter_set() as self.filter_id:
                                self.macro_selection_menu = BannerMenu(container=self.filter_id)
                        with dpg.table(header_row=False):
                            dpg.add_table_column()
                            dpg.add_table_column(init_width_or_weight=25, width_fixed=True)
                            with dpg.table_row():
                                dpg.add_button(label="Add", width=-1, callback=self.__on_create_macro)
                                dpg.add_button(arrow=True, direction=dpg.mvDir_Up, callback=self.__on_arrow_button, user_data=dpg.mvDir_Up)
                            with dpg.table_row():
                                dpg.add_button(label="Remove", width=-1, callback=self.__on_remove_macro)                                                                
                                dpg.add_button(arrow=True, direction=dpg.mvDir_Down, callback=self.__on_arrow_button, user_data=dpg.mvDir_Down)

                    with dpg.child_window(show=False) as self.config_window:
                        with dpg.group(horizontal=True):
                            dpg.add_text("Name:")
                            self.macro_name = dpg.add_input_text(width=-1, hint="Name", callback=self.__on_name_change)
                        dpg.add_text("Text:")
                        self.macro_text = dpg.add_input_text(multiline=True, width=-1, height=-1, callback=self.__on_text_changed, no_horizontal_scroll=False)

        self.macro_manager = macro_manager
        self.macro_bindings: dict[SelectableButton,TerminalMacro] = {}
        for macro in self.macro_manager.macros:
            self.__insert_macro(macro)
        self.selected_macro: TerminalMacro = None
    
    def __on_create_macro(self):
        macro = TerminalMacro(self.macro_manager.generate_unique_macro_name(), "")
        self.macro_manager.add_macro(macro)
        self.macro_selection_menu.set_banner(self.__insert_macro(macro))
    
    def __on_remove_macro(self):
        if self.selected_macro is None: return
        self.macro_manager.remove_macro(self.selected_macro)
        active_banner = self.macro_selection_menu.active_banner
        keys = list(self.macro_bindings.keys())
        index = keys.index(active_banner)
        if index + 1 < len(keys): #Go to next by default
            next_banner = keys[index + 1]
        elif index > 0: #Go to previous if no next
            next_banner = keys[index - 1]
        else: #Nothing remains
            next_banner = None
        del self.macro_bindings[active_banner]
        self.macro_selection_menu.remove_banner(active_banner, auto_select=False)
        self.macro_selection_menu.set_banner(next_banner)
        if next_banner is None:
            self.selected_macro = None
            dpg.hide_item(self.config_window)
        else:
            self.__on_macro_selected(next_banner)

    def __insert_macro(self, macro: TerminalMacro):
        button = SelectableButton(macro.name, on_select=self.__on_macro_selected, filter_key=macro.name.lower() + " " + macro.text.lower())
        self.macro_bindings[button] = macro
        self.macro_selection_menu.add_banner(button)
        return button

    def __on_arrow_button(self, sender, app_data, user_data):
        if self.selected_macro is None: return
        #Moving macros when a filter view is active wouldn't make sense. Could see it not move at all when it does.
        #So when moving, force the filter off
        dpg.set_value(self.search_text, "")
        dpg.set_value(self.filter_id, "")
        if user_data == dpg.mvDir_Up:
            new_index = self.macro_selection_menu.get_active_index() - 1
        elif user_data == dpg.mvDir_Down:
            new_index = self.macro_selection_menu.get_active_index() + 1
        else: return
        
        if new_index < 0 or new_index >= len(self.macro_manager.macros): return
        self.macro_selection_menu.set_banner_index(self.macro_selection_menu.active_banner, new_index)
        self.macro_manager.set_macro_index(self.selected_macro, new_index)

    def __on_macro_selected(self, macro_banner: SelectableButton):
        self.selected_macro = self.macro_bindings[macro_banner]
        dpg.set_value(self.macro_text, self.selected_macro.text)
        dpg.set_value(self.macro_name, self.selected_macro.name)
        dpg.show_item(self.config_window)
                
    def __on_name_change(self, sender, app_data, user_data):
        self.selected_macro.name = app_data
        self.macro_selection_menu.active_banner.set_text(self.selected_macro.name)
        dpg.configure_item(self.macro_selection_menu.active_banner.button, filter_key=self.selected_macro.name.lower() + " " + self.selected_macro.text.lower())
        
    def __on_text_changed(self, sender, app_data, user_data):
        self.selected_macro.text = app_data
        self.macro_selection_menu.active_banner.set_text(self.selected_macro.name)
        dpg.configure_item(self.macro_selection_menu.active_banner.button, filter_key=self.selected_macro.name.lower() + " " + self.selected_macro.text.lower())        

    def __on_close(self):
        for button in self.macro_bindings:
            button.delete()
        self.macro_selection_menu.delete()
        dpg.delete_item(self.modal)

        #Auto name anything without a name
        for macro in self.macro_manager.macros:
            if macro.name == "":
                macro.name = self.macro_manager.generate_unique_macro_name()
        
        #Save the macros and tell any listeners to update to potential changes
        self.macro_manager.save()
        self.macro_manager.on_modified._notify()

if __name__ == "__main__":
    from settings_manager import SettingsManager

    settings_manager = SettingsManager()
    macro_manager = MacroManager(settings_manager)

    macro_manager.add_macro(TerminalMacro("debug", "!debug_mode=1"))
    macro_manager.add_macro(TerminalMacro("silence", "!debug_mode=0"))
    macro_manager.add_macro(TerminalMacro("debug", "!cat=1"))

    print(macro_manager.macros)

    dpg.create_context()
    dpg.create_viewport()

    with dpg.window() as primary_window:
        pass

    window = MacroConfigurationWindow(macro_manager)

    dpg.set_primary_window(primary_window, True)

    dpg.show_item_registry()

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
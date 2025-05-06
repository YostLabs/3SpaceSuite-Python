"""
Manages the macros saved/configured for the terminal as well as the
modal window for configuring/modifying macros
"""
from managers.settings_manager import SettingsManager
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

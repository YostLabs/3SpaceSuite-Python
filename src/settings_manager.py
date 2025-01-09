from resource_manager import *
import pathlib
from dataclasses import dataclass

import json

class SettingsManager:

    def __init__(self):
        self.settings_folder = APPLICATION_FOLDER / "settings"
        if not self.settings_folder.exists():
            self.settings_folder.mkdir(parents=True, exist_ok=True)

    def post_init(self):
        pass

    def save(self, fname: str, dictionary):
        location = self.settings_folder / fname
        with location.open('w') as fp:
            json.dump(dictionary, fp)

    def load(self, fname: str):
        location = self.settings_folder / fname
        if not location.exists():
            return None
        with location.open('r') as fp:
            return json.load(fp)

    def cleanup(self):
        pass

    

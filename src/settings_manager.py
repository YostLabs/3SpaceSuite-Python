from resource_manager import *
import pathlib
from dataclasses import dataclass

import json

class SettingsManager:

    DEFAULT_SETTINGS_LOCATION = PLATFORM_FOLDERS_ROAMING.user_config_path / "settings"

    @classmethod
    def save(cls, fname: str, obj, folder: pathlib.Path = None, **kwargs):
        if folder is None:
            folder = cls.DEFAULT_SETTINGS_LOCATION
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)

        location = folder / fname
        with location.open('w') as fp:
            json.dump(obj, fp, **kwargs)

    @classmethod
    def load(cls, fname: str, folder: pathlib.Path = None, **kwargs):
        if folder is None:
            folder = cls.DEFAULT_SETTINGS_LOCATION
        location = folder / fname
        if not location.exists():
            return None
        with location.open('r') as fp:
            try:
                return json.load(fp, **kwargs) #If a json.dump failed, it may contain a partial JSON file that isn't readable. Rather then throw exception, return None
            except:
                return None

    @classmethod
    def cleanup(cls):
        pass

#Singleton class to make it more easy to just save off global settings
#in generic dictionaries and store the results in the manager itself
class GenericSettingsManager:

    LOCAL_PATH = PLATFORM_FOLDERS.user_config_path / "settings"
    ROAMING_PATH = PLATFORM_FOLDERS_ROAMING.user_config_path / "settings"

    @classmethod
    def init(cls, settings_manager: SettingsManager):
        cls.manager = settings_manager
        cls.local_dicts = {}
        cls.roaming_dicts = {}

    @classmethod
    def get_local(cls, key: str, default=None):
        if key in cls.local_dicts:
            return cls.local_dicts[key]
        value = cls.manager.load(f"{key}.json", folder=cls.LOCAL_PATH)
        if value is None:
            if default is None: return None
            cls.local_dicts[key] = default
            return default
        cls.local_dicts[key] = value
        return value
    
    @classmethod
    def get_roaming(cls, key: str, default=None):
        if key in cls.roaming_dicts:
            return cls.roaming_dicts[key]
        value = cls.manager.load(f"{key}.json", folder=cls.ROAMING_PATH)
        if value is None:
            if default is None: return None
            cls.roaming_dicts[key] = default
            return default
        cls.roaming_dicts[key] = value
        return value    
    
    @classmethod
    def save_local(cls, key: str, obj=None):
        if obj is None:
            if key not in cls.local_dicts: return
            obj = cls.local_dicts[key]
        
        cls.manager.save(f"{key}.json", obj, folder=cls.LOCAL_PATH)
    
    @classmethod
    def save_roaming(cls, key: str, obj=None):
        if obj is None:
            if key not in cls.roaming_dicts: return
            obj = cls.roaming_dicts[key]
        
        cls.manager.save(f"{key}.json", obj, folder=cls.ROAMING_PATH)


    

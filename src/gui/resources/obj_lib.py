"""
A place to load the object files one time for the entire application
"""
from managers.resource_manager import *
from yostlabs.graphics.loaders.obj_loader import OBJ
from yostlabs.graphics import resources
from managers.settings_manager import SettingsManager
from yostlabs.tss3.consts import *

import time

class ObjectLibrary:

    #Fail Safe. This should be in the file, but just in case it isn't
    DEFAULT_MODEL_PATH = "DL-3.obj"

    @classmethod
    def init(cls):
        cls.obj_cache: dict[str,OBJ] = {}

        cls.config = SettingsManager.load("sensor_models.json", folder=OBJECT_FOLDER)
        cls.mappings: dict[str|int,dict[str|int,str]] = cls.config["Mapping"]
        cls.models: dict[str,dict] = cls.config["Models"]

        #Loads the initial model on initialization so it is ready to use.
        #The rest will be lazily loaded.
        cls.default_model = cls.getObjFromModelName(cls.getDefaultModelName())

    @classmethod
    def getDefaultModelName(cls):
        return cls.mappings["Default"]

    @classmethod
    def getModelName(cls, family: str|int, variation: int|str = "Base"):
        """
        Gets the Model Name to be used for looking up the actual model file and properties.

        Args:
            family: The family of the sensor as either a string descriptor or ID to be looked up in the mapping.
            variation: The variation of the family to look up. If not found, the Base variation will be used.
        Returns:
            model_name: The model name to be used for looking up the actual model file and properties. If the family is not found, the default
            model name will be returned instead.
        """
        model_variations = cls.mappings.get(family)
        if model_variations is None:
            return cls.getDefaultModelName()
        variation = model_variations.get(variation)
        if variation is None:
            return model_variations.get("Base")
        return variation

    @classmethod
    def getModelNameFromSerialNumber(cls, sn: int):
        """
        Parses the supplied SerialNumber to call getModelName with the correct family and variation.
        """
        if sn is None:
            return cls.getDefaultModelName()
        family_number = (sn & THREESPACE_SN_FAMILY_MSK) >> THREESPACE_SN_FAMILY_POS
        variation = hex((sn & THREESPACE_SN_VARIATION_MSK) >> THREESPACE_SN_VARIATION_POS).lower()
        family = THREESPACE_SN_FAMILY_TO_NAME.get(family_number, family_number)
        return cls.getModelName(family, variation)
    
    @classmethod
    def getAvailableModelNames(cls):
        return list(cls.models.keys())
    
    @classmethod
    def getObjFromModelName(cls, name: str):
        if name in cls.obj_cache:
            return cls.obj_cache[name]

        if name in cls.models:
            base_path = cls.models[name].get("Path", cls.DEFAULT_MODEL_PATH)
            scale = cls.models[name].get("Scale", 1)
        else:
            base_path = cls.DEFAULT_MODEL_PATH
            scale = 1

        absolute_path = cls.__toAbsolute(base_path)
        if absolute_path.exists():
            final_path = absolute_path
        else:
            #If the supplied path is not part of the application resources/user supplied,
            #check the graphics library resources for it.
            final_path = resources.get_model_path(base_path).absolute()
            if not final_path.exists():
                raise FileNotFoundError(f"Model file not found for model {name} at either {absolute_path} or {final_path}")

        print("Loading Model:", final_path)
        start_time = time.perf_counter()
        obj = OBJ(final_path, scale=scale)
        obj.generate()
        end_time = time.perf_counter()
        print(f"Total Load Time: {end_time - start_time}")
        cls.obj_cache[name] = obj

        return obj

    @classmethod
    def getObjFromSerialNumber(cls, sn: int):
        modelname = cls.getModelNameFromSerialNumber(sn)
        return cls.getObjFromModelName(modelname)
    
    @classmethod
    def __toAbsolute(cls, path_name: str) -> pathlib.Path:
        """
        Given a path, returns its location in the OBJECT_FOLDER of
        the application. If the path is already absolute (user supplied)
        this will be skipped. Intended as an easy way to load both user
        supplied and built in models without needing to worry about where the
        models are located on the filesystem.
        """
        path = pathlib.Path(path_name)
        if path.is_absolute():
            return path
        return (OBJECT_FOLDER / path).resolve().absolute()
    
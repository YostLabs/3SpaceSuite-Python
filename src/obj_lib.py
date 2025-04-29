"""
A place to load the object files one time for the entire application
"""
from resource_manager import *
from objloader import OBJ
from settings_manager import SettingsManager
from yostlabs.tss3.consts import *

__YLDEFAULTMODELPATH = "DataLogger/DL3_standard v1.obj"

__YLModelPathDict: dict[str|int,dict[str|int,str]] = None
__YLModelDescDict: dict[str,dict] = None
__YLModelDict: dict[str,OBJ] = {}
    
def init():
    global __YLModelPathDict, __YLModelDescDict, __YLModelDict, __YLDEFAULTMODEL

    config = SettingsManager.load("sensor_models.json", folder=OBJECT_FOLDER)
    __YLModelPathDict = config["Mapping"]
    __YLModelDescDict = config["Models"]
    getObjFromSerialNumber(None) #Load the default model into memory

def __toAbsolute(path_name: str):
    path = pathlib.Path(path_name)
    if path.is_absolute():
        return path
    return (OBJECT_FOLDER / path).resolve().absolute()

def getModelName(family: str|int, variation: int):
    options = __YLModelPathDict.get(family)
    if options is None:
        return __YLModelPathDict.get("Default")
    
    variation_specific = options.get(variation)
    if variation_specific is None:
        return options.get("Base")
    
    return variation_specific

import time

def getObjFromSerialNumber(sn: int):
    global __YLModelDict

    if sn is None:
        modelname = getModelName(None, None)
    else:
        family_number = (sn & THREESPACE_SN_FAMILY_MSK) >> THREESPACE_SN_FAMILY_POS
        variation = hex((sn & THREESPACE_SN_VARIATION_MSK) >> THREESPACE_SN_VARIATION_POS).lower()
        family = THREESPACE_SN_FAMILY_TO_NAME.get(family_number, family_number)
        modelname = getModelName(family, variation)
    
    if modelname in __YLModelDict:
        return __YLModelDict[modelname]

    if modelname not in __YLModelDescDict:
        path = __toAbsolute(__YLDEFAULTMODELPATH)
        scale = 1
    else:
        path = __toAbsolute(__YLModelDescDict[modelname]["Path"])
        scale = __YLModelDescDict[modelname]["Scale"]
    
    print("Loading Model:", path)
    start_time = time.perf_counter()
    obj = OBJ(path, scale=scale)
    mid_time = time.perf_counter()
    obj.generate()
    end_time = time.perf_counter()
    print(f"Total Load Time: {end_time - start_time}")
    __YLModelDict[modelname] = obj

    return obj


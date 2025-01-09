"""
A place to load the object files one time for the entire application
"""
from resource_manager import *
from objloader import OBJ

MiniSensorObj = None

def init():
    global MiniSensorObj
    MiniSensorObj = OBJ(OBJECT_FOLDER / "TSS-EM-2_6.obj")
    MiniSensorObj.generate()
    
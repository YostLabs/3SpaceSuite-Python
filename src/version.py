from managers.resource_manager import RESOURCE_FOLDER

VERSION = "Unknown"

def load_version():
    global VERSION
    try:
        with open(RESOURCE_FOLDER / "version.txt", 'r') as fp:
                VERSION = fp.read()
    except:
        VERSION = "Unknown Version"

def get_version():
    return VERSION
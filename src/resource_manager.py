from platformdirs import PlatformDirs
import pathlib
import sys

APPNAME = "TSS-3 Suite"
INTERNAL_APPNAME = "TSSv3_Suite"
APP_AUTHOR = "YostLabs"

PLATFORM_FOLDERS = PlatformDirs(INTERNAL_APPNAME, APP_AUTHOR, ensure_exists=True)
PLATFORM_FOLDERS_ROAMING = PlatformDirs(INTERNAL_APPNAME, APP_AUTHOR, roaming=True, ensure_exists=True)

APPLICATION_FOLDER = pathlib.Path(__file__).parent.parent

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'): #From PyInstaller. So parent = _internal, want that folders parent
    RESOURCE_FOLDER = pathlib.Path(__file__).with_name("resources")
else:
    RESOURCE_FOLDER = pathlib.Path(__file__).parent.parent / "resources"

FONT_FOLDER = RESOURCE_FOLDER / "fonts"
IMAGE_FOLDER = RESOURCE_FOLDER / "images"
OBJECT_FOLDER = RESOURCE_FOLDER / "ThreeDimension"
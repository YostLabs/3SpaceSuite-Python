import pathlib
import sys

APPLICATION_FOLDER = pathlib.Path(__file__).parent.parent

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'): #From PyInstaller. So parent = _internal, want that folders parent
    RESOURCE_FOLDER = pathlib.Path(__file__).with_name("resources")
else:
    RESOURCE_FOLDER = pathlib.Path(__file__).parent.parent / "resources"

FONT_FOLDER = RESOURCE_FOLDER / "fonts"
IMAGE_FOLDER = RESOURCE_FOLDER / "images"
OBJECT_FOLDER = RESOURCE_FOLDER / "ThreeDimension"
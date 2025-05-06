import dearpygui.dearpygui as dpg
from managers.resource_manager import *

class Texture:

    def __init__(self, path: str):
        self.width, self.height, channels, data = dpg.load_image(path)
        self.texture = dpg.add_static_texture(width=self.width, height=self.height, default_value=data)

logo_texture: Texture = None
setting_icon_texture: Texture = None

def init():
    global logo_texture, setting_icon_texture
    with dpg.texture_registry():
        logo_texture = Texture((IMAGE_FOLDER / "logo.png").as_posix())
        setting_icon_texture = Texture((IMAGE_FOLDER / "setting_gear_icon.png").as_posix())
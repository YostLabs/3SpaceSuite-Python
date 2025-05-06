import dearpygui.dearpygui as dpg

from graphics.gl_texture_renderer import TextureRenderer
from graphics.gl_orientation_window import GlOrientationViewer
from graphics.gl_renderer import GL_Renderer
from graphics.objloader import OBJ

import yostlabs.math.vector as vector
import yostlabs.math.quaternion as yl_quat
import numpy as np

TEXTURE_RENDERER = 0
BASE_TEXTURE = 1
REGISTRATION_COUNT = 2

class OrientationView:

    #Map of sizes to TextureRenderers/Base Textures to minimize the amount of
    #openGL resources that need dedicated while still allowing the user to create
    #orientation views with different texture sizes.
    REGISTERED_TEXTURES: dict[int,TextureRenderer|list|int] = {}

    #Store how openGL maps to sensor space
    GL_AXIS_STR = "xy-z"
    GL_AXIS_INFO = vector.parse_axis_string_info(GL_AXIS_STR)

    def __init__(self, model: OBJ, texture_width: int, texture_height: int, static_size=False):
        self.static_size = static_size
        self.size = (texture_width, texture_height)
        self.viewer = GlOrientationViewer(model, GL_Renderer.text_renderer, GL_Renderer.base_font, texture_width, texture_height)
        self.dirty = False
        self.pixels = None #The actual image data. Stored separately because must seperate rendering and updating the texture
        self.deleted = False

        #Create necessary texture objects or grab the cached versions
        if not self.size in OrientationView.REGISTERED_TEXTURES:
            self.renderer = TextureRenderer(*self.size)
            with self.renderer:
                self.viewer.set_axes_visible(False)
                self.viewer.set_model_visible(False)
                self.viewer.render()
                self.viewer.set_axes_visible(True)
                self.viewer.set_model_visible(True)
            self.base_texture = self.renderer.get_texture_pixels()
            self.base_texture = np.flip(self.base_texture, 0).flatten()
            OrientationView.REGISTERED_TEXTURES[self.size] = { TEXTURE_RENDERER: self.renderer, BASE_TEXTURE: self.base_texture, REGISTRATION_COUNT: 1 }
        else:
            self.renderer = OrientationView.REGISTERED_TEXTURES[self.size][TEXTURE_RENDERER]
            self.base_texture = OrientationView.REGISTERED_TEXTURES[self.size][BASE_TEXTURE]
            OrientationView.REGISTERED_TEXTURES[self.size][REGISTRATION_COUNT] += 1
        
        print(f"{OrientationView.REGISTERED_TEXTURES=}")
        
        with dpg.texture_registry() as self.texture_registry:
            self.texture = dpg.add_raw_texture(width=texture_width, height=texture_height, default_value=self.base_texture, format=dpg.mvFormat_Float_rgba)
        
        if self.static_size:
            self.image = dpg.add_image(self.texture, width=texture_width, height=texture_height)
        else:
            self.image = dpg.add_image(self.texture)

    def render_image(self, quat: list[float], axis_info: list[list[int],list[int],bool], hide_sensor=False, hide_arrows=False):
        """
        Params
        ------
        quat - The orientation to render the model at as a quaternion
        axis_info - A list in the format of axis_order, multipliers, right_handed. The result of vector.parse_axis_string_info
        NOTE: GL rendering MUST happen in the main thread
        """
        #Configuration        
        self.viewer.set_model_visible(not hide_sensor)
        self.viewer.set_axes_visible(not hide_arrows)
        self.viewer.set_axis_info(*axis_info[:2])

        glQuat = yl_quat.quaternion_swap_axes_fast(quat, axis_info, OrientationView.GL_AXIS_INFO)
        self.viewer.set_orientation_quat(glQuat)

        #Actually render the image
        with self.renderer:
            self.viewer.render()
        pixels = self.renderer.get_texture_pixels()
        pixels = np.flip(pixels, 0).flatten()
        self.pixels = pixels

        #Will actually get rendered when update_image is called
        self.dirty = True
    
    def update_image(self):
        if not self.static_size:
            rect = dpg.get_item_rect_size(self.image)
            self.viewer.set_perspective(*rect)
        if not self.dirty: return
        dpg.set_value(self.texture, self.pixels)
        self.dirty = False
    
    def delete(self):
        if self.deleted: return
        if dpg.does_item_exist(self.image):
            dpg.delete_item(self.image)
        dpg.delete_item(self.texture_registry)
        self.viewer.delete()
        OrientationView.REGISTERED_TEXTURES[self.size][REGISTRATION_COUNT] -= 1

        #Clean up the registration
        if OrientationView.REGISTERED_TEXTURES[self.size][REGISTRATION_COUNT] == 0:
            OrientationView.REGISTERED_TEXTURES[self.size][TEXTURE_RENDERER].destroy()
            del OrientationView.REGISTERED_TEXTURES[self.size]
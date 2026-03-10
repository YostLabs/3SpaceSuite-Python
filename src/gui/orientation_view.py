import dearpygui.dearpygui as dpg

from yostlabs.graphics import GL_Context, ModelObject, TextureRenderer, OBJ
from yostlabs.graphics.scene_prefabs import OrientationScene
from yostlabs.graphics.dpg import DpgScene

from yostlabs.math.axes import AxisOrder

TEXTURE_RENDERER = 0
BASE_TEXTURE = 1
REGISTRATION_COUNT = 2

#Wrapper around yostlabs graphics object to reduce the number of duplicate
#openGL and DPG resources needed. Primary reduction is via reduced TextureRenderers
#which reduces the number of framebuffers, and also reduced DPG texture objects.
#Also handles additional logic for screen resizing, although that should probably be
#moved into the DPG Scene.

class OrientationView:

    #Map of sizes to TextureRenderers/Base Textures to minimize the amount of
    #openGL resources that need dedicated while still allowing the user to create
    #orientation views with different texture sizes.
    REGISTERED_TEXTURES: dict[int,TextureRenderer|list|int] = {}

    def __init__(self, model: OBJ, texture_width: int, texture_height: int, static_size=False, axis_compass_display=True):
        self.static_size = static_size
        self.size = (texture_width, texture_height)
        self.orientation_scene = OrientationScene(texture_width, texture_height, model=ModelObject(model=model), font=GL_Context.default_font)
        self.orientation_scene.orientation_indicator.set_visible(axis_compass_display)
        self.dirty = False
        self.deleted = False

        #Create necessary texture objects or grab the cached versions
        if not self.size in OrientationView.REGISTERED_TEXTURES:
            self.renderer = TextureRenderer(*self.size)
            self.dpg_scene = DpgScene(texture_width, texture_height, self.orientation_scene, renderer=self.renderer)
            with self.renderer:
                self.orientation_scene.axes.set_visible(False)
                self.orientation_scene.model.set_visible(False)
                self.dpg_scene.render()
                self.orientation_scene.axes.set_visible(True)
                self.orientation_scene.model.set_visible(True)
            self.base_texture = self.dpg_scene.get_texture_data()
            OrientationView.REGISTERED_TEXTURES[self.size] = { TEXTURE_RENDERER: self.renderer, BASE_TEXTURE: self.base_texture, REGISTRATION_COUNT: 1 }
        else:
            self.renderer = OrientationView.REGISTERED_TEXTURES[self.size][TEXTURE_RENDERER]
            self.base_texture = OrientationView.REGISTERED_TEXTURES[self.size][BASE_TEXTURE]
            OrientationView.REGISTERED_TEXTURES[self.size][REGISTRATION_COUNT] += 1
            self.dpg_scene = DpgScene(texture_width, texture_height, self.orientation_scene, renderer=self.renderer)
        
        with dpg.texture_registry() as self.texture_registry:
            self.texture = dpg.add_raw_texture(width=texture_width, height=texture_height, default_value=self.base_texture, format=dpg.mvFormat_Float_rgba)
        
        if self.static_size:
            self.image = dpg.add_image(self.texture, width=texture_width, height=texture_height)
        else:
            self.image = dpg.add_image(self.texture)

    def set_model(self, model: OBJ):
        self.orientation_scene.set_model(ModelObject(model=model))

    def render_image(self, quat: list[float], axis_order: AxisOrder, hide_sensor=False, hide_arrows=False):
        """
        Params
        ------
        quat - The orientation to render the model at as a quaternion
        axis_info - A list in the format of axis_order, multipliers, right_handed. The result of vector.parse_axis_string_info
        NOTE: GL rendering MUST happen in the main thread
        """
        #Configuration   
        self.orientation_scene.model.set_visible(not hide_sensor)
        self.orientation_scene.axes.set_visible(not hide_arrows)
        self.orientation_scene.set_axis_order(axis_order)
        self.orientation_scene.set_model_rotation_quat(quat)

        #Actually render the image
        self.dpg_scene.render()
        self.dirty = True
        #Caches the texture data. This is done to ensure the data is cached during the main thread.
        #Doing OpenGL calls during a DPG thread, which is allowed to call update_image which calls this,
        #would error due to OpenGL calls not being allowed in DPG threads.
        self.dpg_scene.get_texture_data()

    def update_image(self):
        if not self.static_size:
            self.dpg_scene.scale_to_image(self.image)
        if not self.dirty: return
        self.dpg_scene.update_dpg_texture(self.texture)
        self.dirty = False
    
    def delete(self):
        if self.deleted: return
        if dpg.does_item_exist(self.image):
            dpg.delete_item(self.image)
        dpg.delete_item(self.texture_registry)
        self.dpg_scene.destroy()
        OrientationView.REGISTERED_TEXTURES[self.size][REGISTRATION_COUNT] -= 1

        #Clean up the registration
        if OrientationView.REGISTERED_TEXTURES[self.size][REGISTRATION_COUNT] == 0:
            renderer: TextureRenderer = OrientationView.REGISTERED_TEXTURES[self.size][TEXTURE_RENDERER]
            renderer.destroy()
            del OrientationView.REGISTERED_TEXTURES[self.size]
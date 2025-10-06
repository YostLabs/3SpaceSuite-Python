
from graphics.objloader import OBJ
from graphics.gl_texture_renderer import TextureRenderer
from graphics.gl_font_loader import Font, TextRenderer
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np

import yostlabs.math.quaternion as yl_quat

EXAMPLE_TEXTURE_WIDTH = 200
EXAMPLE_TEXTURE_HEIGHT = 200

"""
"""
class GlOrientationViewer:

    #These are the arrows that will always be used for the top left display
    DEFAULT_ARROWS = None

    ARROW_ORDER = [((1, 0, 0), 'X'), ((0, 1, 0), 'Y'), ((0, 0, 1), 'Z')]

    def __init__(self, model: OBJ, text_renderer: TextRenderer, font: Font, 
                 draw_width=800, draw_height=600,
                 background_color=[105 / 255, 105 / 255, 105 / 255, 1], model_arrows=True, tl_arrows=True):
        self.arrows = model_arrows or tl_arrows
        self.model_arrows = model_arrows
        self.tl_arrows = tl_arrows

        self.text_renderer = text_renderer
        self.font = font

        #The model that will be rotating
        self.model_visible = True
        self.axes_visible = True
        self.model = model #TODO: Make me scalable        

        self.axis_renderer = None
        self.axis_order = [0, 1, 2]
        self.axis_multipliers = [1, 1, 1]
        self.z = -80
        
        #Create texture/renderer for the top left arrows
        if self.arrows:
            if GlOrientationViewer.DEFAULT_ARROWS is None:
                GlOrientationViewer.DEFAULT_ARROWS = glGenLists(1)
                glNewList(GlOrientationViewer.DEFAULT_ARROWS, GL_COMPILE)
                draw3DArrow(0.7, 18, 3.5, 6)
                glEndList()

            #The axes shown in the top left are first drawn as a texture and then saved off so no additional computations are needed
            #and can just draw directly to a rectangle
            if self.tl_arrows:
                self.axis_renderer = TextureRenderer(EXAMPLE_TEXTURE_WIDTH, EXAMPLE_TEXTURE_HEIGHT)
                with self.axis_renderer:
                    renderExampleAxes(GlOrientationViewer.DEFAULT_ARROWS, [0, 1, 2],
                                    EXAMPLE_TEXTURE_WIDTH, EXAMPLE_TEXTURE_HEIGHT, 30,
                                    self.text_renderer, self.font, 28)        


        self.width = draw_width
        self.height = draw_height
        self.background_color = background_color
        self.view_perspective = (self.width, self.height)

        self.data_type = "quat"
        self.orientation = np.array([0, 0, 0, 1], dtype=np.float32)

    def set_orientation_quat(self, quat: list[float]):
        self.data_type = "quat"
        self.orientation = quat

    def set_orientation_matrix(self, matrix: list[float]):
        self.data_type = "matrix"
        if len(matrix) == 9:
            matrix = np.array(matrix).reshape((3, 3))
        self.orientation = matrix

    def set_model(self, model: OBJ):
        self.model = model

    def set_model_visible(self, visible: bool):
        self.model_visible = visible
    
    def set_axes_visible(self, visible: bool):
        self.axes_visible = visible

    def set_compass_visible(self, visible: bool):
        self.tl_arrows = visible

    def set_axis_info(self, order: list[int], multipliers: list[int]):
        self.axis_order = order
        self.axis_multipliers = multipliers

    def set_perspective(self, width, height):
        self.view_perspective = (width, height)

    def set_distance(self, z: int = 80):
        self.z = -abs(z)

    def __render_model(self):
        glViewport(0, 0, self.width, self.height)

        glEnable(GL_LIGHTING)
        glBindTexture(GL_TEXTURE_2D, 0)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(90.0, self.view_perspective[0] / self.view_perspective[1], 1, 150.0) #TODO: Change my FOV probably
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        #Setup rotation of model
        if self.data_type == "quat":
            matrix = yl_quat.quaternion_to_3x3_rotation_matrix(self.orientation)
        else:
            matrix = self.orientation

        #Convert the 3x3 rotation matrix to the 4x4 model matrix
        model_matrix = np.identity(4)
        model_matrix[:3,:3] = matrix

        glTranslate(0, 0, self.z) #TODO: Change me

        #Use the transpose because openGL expects column major, but numpy stores in row major
        glMultMatrixf(model_matrix.T)

        #-----------------------------Render the model--------------------------------
        glColor(1, 1, 1, 1)
        if self.model_visible:
            self.model.render()

        #-----------------------------Render its axes----------------------------------
        if self.model_arrows and self.axes_visible:
            # LETTER_OFFSET = 28 #TODO CHANGE ME
            #X
            color, letter = self.ARROW_ORDER[self.axis_order.index(0)]
            mult = self.axis_multipliers[self.axis_order.index(0)]
            self.render_arrow(yl_quat.quat_from_axis_angle([0, 1, 0], np.radians(-90)), color, mult, letter)
            #Y
            color, letter = self.ARROW_ORDER[self.axis_order.index(1)]
            mult = self.axis_multipliers[self.axis_order.index(1)]
            self.render_arrow(yl_quat.quat_from_axis_angle([1, 0, 0], np.radians(90)), color, mult, letter)

            #Z
            color, letter = self.ARROW_ORDER[self.axis_order.index(2)]
            mult = self.axis_multipliers[self.axis_order.index(2)]
            self.render_arrow([0, 0, 0, 1], color, mult, letter)

    def render_arrow(self, quat: list[float], color: tuple[float,float,float], size: float, text=None, no_grotate=False):
        LETTER_OFFSET = 28 #TODO CHANGE ME

        #Setup rotation of model
        matrix = yl_quat.quaternion_to_3x3_rotation_matrix(quat)

        #Convert the 3x3 rotation matrix to the 4x4 model matrix
        model_matrix = np.identity(4)
        model_matrix[:3,:3] = matrix

        glPushMatrix()
        if no_grotate:
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            glTranslate(0, 0, self.z) #TODO: Change me

        glColor(*color, 1)
        glMultMatrixf(model_matrix.T)
        #glRotate(-90, 0, 1, 0)
        glScale(1, 1, 1 * size)
        glCallList(GlOrientationViewer.DEFAULT_ARROWS)
        if text is not None:
            glTranslate(0, 0, -LETTER_OFFSET)
            projection = glGetFloatv(GL_PROJECTION_MATRIX)
            mv = glGetFloatv(GL_MODELVIEW_MATRIX)    
            mv[:3,:3] = np.identity(3)
            mvp = mv @ projection
            self.text_renderer.render_text(self.font, text, 0, 0, 0.1, color, mvp, centered=True)          
        glPopMatrix()

    def render(self):
        glClearColor(*self.background_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
    
        self.__render_model()

        #------------------------------RENDER THE TOP LEFT DIAGRAM----------------------------------
        #Done last because it has transparency
        if self.tl_arrows:
            #Position it to render in the top left of the viewport
            glViewport(int(-EXAMPLE_TEXTURE_WIDTH * 0.3), self.height-EXAMPLE_TEXTURE_HEIGHT-10, EXAMPLE_TEXTURE_WIDTH, EXAMPLE_TEXTURE_HEIGHT)
            renderTextureToViewport(self.axis_renderer.texture)
    
    def delete(self):
        if self.axis_renderer is not None:
            self.axis_renderer.destroy()
            self.axis_renderer = None

    @staticmethod
    def configureGlSettings():
        glEnable(GL_LIGHTING)

        #No ambient from base model, purely from lighting
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (0, 0, 0, 0)) 

        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION,  (0, 0, 1, 0)) #Because 0, this is just a directional light, not position based
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.2, 0.2, 0.2, 1.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.7, 0.7, 0.7, 1.0))

        #This is what allows lighting to track the color of materials when drawing
        glEnable(GL_COLOR_MATERIAL)

        #Necessary for scale operations
        glEnable(GL_RESCALE_NORMAL)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)

#Helper
def draw3DArrow(stick_width: float, stick_length: float, triangle_width: float, triangle_length: float):
    hsw = stick_width / 2
    htw = triangle_width / 2
    tip_length = stick_length + triangle_length

    glFrontFace(GL_CCW)

    glBegin(GL_QUADS)

    #Back Face/CCW
    glNormal(0, 0, 1)
    glVertex(-hsw, -hsw, 0)
    glVertex(hsw, -hsw, 0)
    glVertex(hsw, hsw, 0)
    glVertex(-hsw, hsw, 0)

    #Right/CCW
    glNormal(1, 0, 0)
    glVertex(hsw, hsw, 0)
    glVertex(hsw, -hsw, 0)
    glVertex(hsw, -hsw, -stick_length)
    glVertex(hsw, hsw, -stick_length) 

    #Top/CCW
    glNormal(0, 1, 0)
    glVertex(-hsw, hsw, 0)
    glVertex(hsw, hsw, 0)
    glVertex(hsw, hsw, -stick_length)
    glVertex(-hsw, hsw, -stick_length)

    #Left/CCW
    glNormal(-1, 0, 0)
    glVertex(-hsw, hsw, 0)
    glVertex(-hsw, hsw, -stick_length)
    glVertex(-hsw, -hsw, -stick_length)
    glVertex(-hsw, -hsw, 0)

    #Bottom/CCW
    glNormal(0, -1, 0)
    glVertex(-hsw, -hsw, 0)
    glVertex(-hsw, -hsw, -stick_length)
    glVertex(hsw, -hsw, -stick_length)
    glVertex(hsw, -hsw, 0)

    #Pyramid Base/CCW
    glNormal(0, 0, 1)    
    glVertex(-htw, -htw, -stick_length)
    glVertex(htw, -htw, -stick_length)
    glVertex(htw, htw, -stick_length)
    glVertex(-htw, htw, -stick_length)

    glEnd()

    glBegin(GL_TRIANGLES)

    #Right Triangle/CCW
    br = np.array([htw, -htw, -stick_length])
    tip = np.array([0, 0, -tip_length])
    bl = np.array([htw, htw, -stick_length])
    base = br - bl
    up = tip - bl
    normal = np.cross(base, up)
    normal /= np.linalg.norm(normal)
    glNormal(*normal)
    glVertex(*br)
    glVertex(*tip)
    glVertex(bl)

    #Top Triangle/CCW
    br = np.array([htw, htw, -stick_length])
    bl = np.array([-htw, htw, -stick_length])
    base = br - bl
    up = tip - bl
    normal = np.cross(base, up)
    normal /= np.linalg.norm(normal) 
    glNormal(*normal)
    glVertex(*br)
    glVertex(*tip)
    glVertex(*bl)

    #Left Triangle/CCW
    br = np.array([-htw, htw, -stick_length])
    bl = np.array([-htw, -htw, -stick_length])
    base = br - bl
    up = tip - bl
    normal = np.cross(base, up)
    normal /= np.linalg.norm(normal)  
    glNormal(*normal)    
    glVertex(*br)
    glVertex(*tip)
    glVertex(*bl)
    
    #Bottom Triangle/CCW
    br = np.array([-htw, -htw, -stick_length])
    bl = np.array([htw, -htw, -stick_length])
    base = br - bl
    up = tip - bl
    normal = np.cross(base, up)
    normal /= np.linalg.norm(normal) 
    glNormal(*normal)     
    glVertex(*br)
    glVertex(*tip)
    glVertex(*bl)

    glEnd()

def renderExampleAxes(arrow_list: int, order: list[int], 
                      width: int, height: int, fov: int,
                      text_renderer: TextRenderer, font: Font, letter_offset: int):
    """
    Renders the axes that should be displayed in the top left.
    Default order should be [0, 1, 2] for [x, y, z]. Changing order will change
    the color of the axes and the letter next to them.
    """
    
    glEnable(GL_LIGHTING)
    #Setup the matrices
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fov, width / height, 1, 150.0)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    #Now draw the desired thing into the frame buffer/texture
    glClearColor(0, 0, 0, 0) #Transparent background
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    SCALE = 0.7
    glTranslate(0, 0, -80)
    glScale(SCALE, SCALE, SCALE)

    #X
    glPushMatrix()
    glColor(1, 0, 0, 1)
    glRotate(-90, 0, 1, 0)
    glCallList(arrow_list)
    glTranslate(0, 0, -letter_offset)
    projection = glGetFloatv(GL_PROJECTION_MATRIX)
    mv = glGetFloatv(GL_MODELVIEW_MATRIX)    
    mv[:3,:3] = np.identity(3)
    mvp = mv @ projection
    text_renderer.render_text(font, "X", 0, 0, 0.1, [1, 0, 0], mvp, centered=True)      
    glPopMatrix()

    #Y
    glPushMatrix()
    glColor(0, 1, 0, 1)
    glRotate(90, 1, 0, 0)
    glCallList(arrow_list)
    glTranslate(0, 0, -letter_offset)
    projection = glGetFloatv(GL_PROJECTION_MATRIX)
    mv = glGetFloatv(GL_MODELVIEW_MATRIX)    
    mv[:3,:3] = np.identity(3)
    mvp = mv @ projection
    text_renderer.render_text(font, "Y", 0, 0, 0.1, [0, 1, 0], mvp, centered=True)      
    glPopMatrix()

    #Z
    glPushMatrix()
    glColor(0, 0, 1, 1)
    glCallList(arrow_list)
    glTranslate(0, 0, -letter_offset)
    projection = glGetFloatv(GL_PROJECTION_MATRIX)
    mv = glGetFloatv(GL_MODELVIEW_MATRIX)
    mv[:3,:3] = np.identity(3)
    mvp = mv @ projection
    text_renderer.render_text(font, "Z", -4, 0.5, 0.1, [0, 0, 1], mvp, centered=True)
    glPopMatrix()
    glDisable(GL_LIGHTING)

def renderTextureToViewport(texture):
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor(1, 1, 1, 1) #The vertex color gets multiplied by the texture color, so make all 1
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture)

    #Reset the matrix stack
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    #Draw the quad with the rendered texture!
    glBegin(GL_QUADS)
    glTexCoord(0, 0)
    glVertex(-1, -1, 0)
    glTexCoord(1, 0)
    glVertex(1, -1, 0)
    glTexCoord(1, 1)
    glVertex(1, 1, 0)
    glTexCoord(0, 1)
    glVertex(-1, 1, 0)
    glEnd()
    
    #Cleanup
    glDisable(GL_BLEND)
    glDisable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, 0)
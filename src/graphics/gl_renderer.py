import glfw
from OpenGL.GL import *
from OpenGL.GLU import *

from graphics.gl_font_loader import TextRenderer, Font

class GL_Renderer:
    initialized = False

    @classmethod
    def init(cls):
        if cls.initialized: return
        if not glfw.init():
            print("Failed to init Glfw")
            return
        
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        window = glfw.create_window(200, 200, "My Window", None, None) #Size and name doesn't matter, just needs to exist so openGL functions work
        if not window:
            glfw.terminate()
            print("Glfw window can't be created")
            exit()
        glfw.make_context_current(window)

        #--SETUP LIGHTING--
        glLightfv(GL_LIGHT0, GL_POSITION,  (-40, 200, 100, 0.0))
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.2, 0.2, 0.2, 1.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.5, 0.5, 0.5, 1.0))
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHTING)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_DEPTH_TEST)
        glShadeModel(GL_SMOOTH)           # most obj files expect to be smooth-shaded

        cls.initialized = True
        
        cls.text_renderer = TextRenderer()
        cls.base_font: Font = None

    @classmethod
    def set_font(cls, path: str, size: int):
        cls.base_font = Font(path, size)

    @classmethod
    def cleanup(self):
        glfw.terminate()

    
        
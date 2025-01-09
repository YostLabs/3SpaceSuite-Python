import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
from yostlabs.math import quaternion

import numpy as np

from objloader import *

import time

class GL_Object:

    def __init__(self, path: str=None, obj: OBJ = None, width: int = 200, height: int = 200, z=2):
        self.obj_manually_generated = False
        if obj: #This is done because generating the OBJ takes a long time. More efficent to resuse the obj
            self.obj = obj
        elif path is not None:
            self.obj = OBJ(path)
            self.obj.generate()
            self.obj_manually_generated = True
        else:
            raise ValueError("Must provide path or obj")

        self.z = z
        self.texture_width = width
        self.texture_height = height
        self.view_perspective = (width, height)

        self.quat = [0, 0, 0, 1]

        #Create an FBO for this object to use
        self.depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.texture_width, self.texture_height)

        self.color_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)        
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.texture_width, self.texture_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)

        self.framebuffer = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_buffer)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.color_texture, 0)

        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            print("Incomplete frame buffer object:", status)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        self.__hide_object = False

        self.color = (0, 0, 0, 1)

    def hide_obj(self, hide: bool):
        self.__hide_object = hide

    def set_background_color(self, r, g, b, a):
        """
        Takes RGBA as floats
        """
        self.color = (r, g, b, a)

    def set_rotation_quat(self, quat: list[float]):
        self.quat = quat[:]

    def set_view_perspective(self, width, height):
        self.view_perspective = (width, height)

    def render(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        glViewport(0, 0, self.texture_width, self.texture_height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(90.0, self.view_perspective[0] / self.view_perspective[1], 1, 100.0)
        glEnable(GL_DEPTH_TEST)

        glMatrixMode(GL_MODELVIEW)
        glClearColor(*self.color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        #Convert quat into worldspace and into visual space from default sensor orientation
        quat = quaternion.quat_inverse(self.quat)
        matrix = quaternion.quaternion_to_3x3_rotation_matrix(quat)
        #DPG: X = Left, Y = Down, Z = In
        #OpenGL: X = Right, Y = Up, Z = Viewer
        #Sensor: X = East/Right, Y = Up, Z = North/In If left handed
        #For OpenGL, negate x and y, reason is because different handedness, so negate all, and then z should be negated cause different
        matrix = np.array([
            [matrix[0][0], matrix[0][1], -matrix[0][2], 0],
            [matrix[1][0], matrix[1][1], -matrix[1][2], 0],
            [-matrix[2][0], -matrix[2][1], matrix[2][2], 0],
            [0, 0, 0, 1]
        ])

        glTranslate(0, 0, -self.z)
        glMultMatrixf(matrix)

        if not self.__hide_object:
            self.obj.render()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    
    def get_texture(self):
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        pixel_data = glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_FLOAT)
        pixel_data = pixel_data.reshape((self.texture_height, self.texture_width, 4)) #For some reason the getTexImage returns the wrong shape
        pixel_data = np.flip(pixel_data, 0)
        glBindTexture(GL_TEXTURE_2D, 0)

        return pixel_data
    
    def delete(self):
        if self.obj_manually_generated:
            self.obj.free()

        glDeleteRenderbuffers(1, [self.depth_buffer])
        glDeleteTextures(1, [self.color_texture])
        glDeleteFramebuffers(1, [self.framebuffer])



class GL_Renderer:
    initialized = False

    @classmethod
    def init(self):
        if self.initialized: return
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

        self.initialized = True

    @classmethod
    def cleanup(self):
        glfw.terminate()
        
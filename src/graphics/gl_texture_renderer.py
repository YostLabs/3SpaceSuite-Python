"""
Helper for rendering to a texture
"""
from OpenGL.GL import *

class TextureRenderer:

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

        self.framebuffer = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)

        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None) #Fill with no data, make sure has alpha channel
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

        #Need a depth buffer because rendering a 3D image into this texture
        self.depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.width, self.height)

        #Finish configuring the Framebuffer
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_buffer)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.texture, 0)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            print("Incomplete frame buffer object:", status)
            exit()

        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        self.cached_viewport = [0, 0, 0, 0]

    def __enter__(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        self.cached_viewport = glGetIntegerv(GL_VIEWPORT)
        glViewport(0, 0, self.width, self.height)
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(*self.cached_viewport)

    def get_texture_pixels(self):
        glBindTexture(GL_TEXTURE_2D, self.texture)
        pixel_data = glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_FLOAT)
        pixel_data = pixel_data.reshape((self.height, self.width, 4)) #For some reason the getTexImages returns the wrong shape
        glBindTexture(GL_TEXTURE_2D, 0)

        return pixel_data

    def clean(self):
        if self.framebuffer is None: return

        glDeleteFramebuffers(1, [self.framebuffer])
        glDeleteRenderbuffers(1, [self.depth_buffer])
        self.framebuffer = None
        self.depth_buffer = None

    def destroy(self):
        self.clean()
        if self.texture is None: return
        glDeleteTextures(1, [self.texture])
        self.texture = None
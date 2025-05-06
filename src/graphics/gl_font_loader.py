import glfw
from OpenGL.GL import *
from OpenGL.GL import shaders
import freetype
import numpy as np
from dataclasses import dataclass

@dataclass
class Glyph:
    texture_id: int         #Open GL texture handle
    size: np.ndarray        #Size of glyph
    bearing: np.ndarray     #Offset from baseline to left/top of glyph
    advance: int            #Offset to next glyph (In 1/64th pixels)

class Font:

    def __init__(self, path: str, pixel_height: int):
        self.face = freetype.Face(path)
        self.face.set_pixel_sizes(0, pixel_height)

        self.glyphs: dict[str, Glyph] = {}

    def load_character(self, char: str):
        if char in self.glyphs: return

        self.face.load_char(char)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, self.face.glyph.bitmap.width, self.face.glyph.bitmap.rows, 0, GL_RED, GL_UNSIGNED_BYTE, self.face.glyph.bitmap.buffer)

        #Set texture options
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        #Save off the texture
        glyph = Glyph(texture,
                      np.array([self.face.glyph.bitmap.width, self.face.glyph.bitmap.rows], dtype=np.int32),   #Size
                      np.array([self.face.glyph.bitmap_left, self.face.glyph.bitmap_top], dtype=np.int32),     #Bearing
                      self.face.glyph.advance.x
                      )
        self.glyphs[char] = glyph

        glPixelStorei(GL_UNPACK_ALIGNMENT, 4) #Set back

class TextRenderer:

    VERTEX_SOURCE = \
"""
#version 330
layout (location = 0) in vec4 vertex; // <vec2 pos, vec2 tex>
out vec2 TexCoords;

uniform mat4 projection;

void main()
{
    gl_Position = projection * vec4(vertex.xy, 0.0, 1.0);
    TexCoords = vertex.zw;
}  
"""

    FRAG_SOURCE = \
"""
#version 330
in vec2 TexCoords;
out vec4 color;

uniform sampler2D text;
uniform vec3 textColor;

void main()
{    
    vec4 sampled = vec4(1.0, 1.0, 1.0, texture(text, TexCoords).r);
    color = vec4(textColor, 1.0) * sampled;
}  
"""

    def __init__(self):
        self.textProgram = shaders.compileProgram(
            shaders.compileShader(TextRenderer.VERTEX_SOURCE, GL_VERTEX_SHADER),
            shaders.compileShader(TextRenderer.FRAG_SOURCE, GL_FRAGMENT_SHADER)
        )

        # configure VAO/VBO for texture quads
        # -----------------------------------
        self.VAO = glGenVertexArrays(1)
        self.VBO = glGenBuffers(1)
        glBindVertexArray(self.VAO)
        glBindBuffer(GL_ARRAY_BUFFER, self.VBO)
        glBufferData(GL_ARRAY_BUFFER, sizeof(ctypes.c_float) * 6 * 4, None, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 4 * sizeof(ctypes.c_float), None)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def render_text(self, font: Font, text: str, x: float, y: float, scale: float, color: list, matrix: np.ndarray = None, centered = False):
        if len(text) == 0: return
        glUseProgram(self.textProgram)
        glUniform3f(glGetUniformLocation(self.textProgram, "textColor"), *color[:3])
        if matrix is not None:
            glUniformMatrix4fv(glGetUniformLocation(self.textProgram, "projection"), 1, GL_FALSE, matrix)
        glActiveTexture(GL_TEXTURE0)
        glBindVertexArray(self.VAO)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        #First character starts centered at given position
        if centered:
            c = text[0]
            if c not in font.glyphs:
                font.load_character(c)
            glyph = font.glyphs[c]

            w = glyph.size[0] * scale
            h = glyph.size[1] * scale

            x -= glyph.bearing[0] * scale
            x -= w / 2

            y -= (glyph.size[1] - glyph.bearing[1]) * scale
            y -= h / 2

        for c in text:
            if c not in font.glyphs:
                font.load_character(c)
            glyph = font.glyphs[c]


            xpos = x + glyph.bearing[0] * scale
            ypos = y - (glyph.size[1] - glyph.bearing[1]) * scale

            w = glyph.size[0] * scale
            h = glyph.size[1] * scale

            #Update VBO
            vertices = np.array([
                [ xpos,     ypos + h,   0.0, 0.0 ],            
                [ xpos,     ypos,       0.0, 1.0 ],
                [ xpos + w, ypos,       1.0, 1.0 ],

                [ xpos,     ypos + h,   0.0, 0.0 ],
                [ xpos + w, ypos,       1.0, 1.0 ],
                [ xpos + w, ypos + h,   1.0, 0.0 ]
            ], dtype=np.float32)
          
            glBindTexture(GL_TEXTURE_2D, glyph.texture_id)

            #Update the VBO so the shape of the quad matches the shape of the character
            glBindBuffer(GL_ARRAY_BUFFER, self.VBO)
            glBufferSubData(GL_ARRAY_BUFFER, 0, vertices.nbytes, vertices)

            glDrawArrays(GL_TRIANGLES, 0, 6)

            x += (glyph.advance >> 6) * scale  
        glBindVertexArray(0)
        glDisable(GL_BLEND)
        glUseProgram(0)
        glBindTexture(GL_TEXTURE_2D, 0)


if __name__ == "__main__":
    if not glfw.init():
        print("Failed to init GLFW")
        exit()

    WIDTH = 800
    HEIGHT = 800

    window = glfw.create_window(WIDTH, HEIGHT, "My Playground", None, None)
    if not window:
        glfw.terminate()
        print("Glfw window can't be created")
        exit()

    glfw.make_context_current(window)

    from OpenGL.GLU import *

    text_renderer = TextRenderer()
    font = Font("comic.ttf", 48)
    while not glfw.window_should_close(window):
        glfw.poll_events()

        #Clear
        glClearColor(0.25, 0.25, 0.25, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, 1000, -10, 1000)
        mat = glGetFloatv(GL_PROJECTION_MATRIX)

        text_renderer.render_text(font, "Hello", 0, 0, 1, [1, 0, 0], matrix=mat)

        glfw.swap_buffers(window)


    glfw.terminate()
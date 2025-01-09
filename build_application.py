import glfw.library
import PyInstaller.__main__
import pathlib

debug = False

cmd_properties = []
cmd_properties.append(f'src/main.py')
cmd_properties.append(f"--paths=src")
#cmd_properties.append(f'--specpath=src')
cmd_properties.append(f"--add-binary={glfw.library.glfw._name}:glfw")
cmd_properties.append(f"--add-data=resources:resources")
cmd_properties.append(f"--icon=resources/images/icon.ico")
cmd_properties.append(f"--splash=resources/images/logo.jpg")
cmd_properties.append(f"--noconfirm")

if not debug:
    cmd_properties.append(f"--name=3.0-Space Suite")
    cmd_properties.append(f"--noconsole")
else:
    cmd_properties.append(f"--name=3.0-Space Suite DEV")

PyInstaller.__main__.run(cmd_properties)
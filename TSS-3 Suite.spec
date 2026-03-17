# -*- mode: python ; coding: utf-8 -*-
import os
import platform
import pathlib
import glfw.library
from PyInstaller.utils.hooks import collect_all

debug = False

# Optional override from environment (used by build_application.py)
debug_override = os.environ.get('TSS3_DEBUG_BUILD')
if debug_override is not None:
    debug = debug_override.strip().lower() in ('1', 'true', 'yes', 'on')

app_name = 'TSS-3 Suite DEV' if debug else 'TSS-3 Suite'
project_root = pathlib.Path(globals().get('SPECPATH', os.getcwd())).resolve()
main_script = project_root / 'src' / 'main.py'
icon_path = project_root / 'resources' / 'images' / 'icon.ico'
logo_path = project_root / 'resources' / 'images' / 'logo.jpg'

datas = [('resources', 'resources')]
binaries = [(glfw.library.glfw._name, 'glfw')]
hiddenimports = []
tmp_ret = collect_all('yostlabs.graphics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [str(main_script)],
    pathex=[str(project_root / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
splash = None
if platform.system() == 'Windows':
    splash = Splash(
        str(logo_path),
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )

exe_args = [pyz, a.scripts]
if splash is not None:
    exe_args.append(splash)
exe_args.append([])

exe = EXE(
    *exe_args,
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=debug,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_path)],
)
collect_args = [exe, a.binaries, a.datas]
if splash is not None:
    collect_args.append(splash.binaries)

coll = COLLECT(
    *collect_args,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)

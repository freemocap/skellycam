# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
import cv2
import os
import platform

datas = []
binaries = []
hiddenimports = ["encodings.idna"]

# Collect all for cv2 (only once)
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')
datas.extend(cv2_datas)
binaries.extend(cv2_binaries)
hiddenimports.extend(cv2_hiddenimports)

# Add specific cv2 modules that might be missed
hiddenimports.extend([
    'cv2.cv2',
    'cv2.rotate',
    'cv2.data',  # For haarcascade files
    'cv2.aruco',
    'cv2.bgsegm',
    'cv2.bioinspired',
    'cv2.ccalib',
    'cv2.cuda',
    'cv2.datasets',
    'cv2.dnn',
    'cv2.dpm',
    'cv2.face',
    'cv2.fisheye',
    'cv2.flann',
    'cv2.freetype',
    'cv2.ft',
    'cv2.hfs',
    'cv2.img_hash',
    'cv2.line_descriptor',
    'cv2.ogl',
    'cv2.omi',
    'cv2.optflow',
    'cv2.plot',
    'cv2.reg',
    'cv2.rgbd',
    'cv2.saliency',
    'cv2.shape',
    'cv2.stereo',
    'cv2.structured_light',
    'cv2.text',
    'cv2.tracking',
    'cv2.videoio',
    'cv2.videostab',
    'cv2.xfeatures2d',
    'cv2.ximgproc',
    'cv2.xphoto',
])

# Add the directory containing cv2 DLLs
cv2_path = os.path.dirname(cv2.__file__)
if platform.system=="Windows":
    binaries.append((os.path.join(cv2_path, '*.dll'), '.'))
elif platform.system=="Darwin":
    binaries.append((os.path.join(cv2_path, '*.dylib'), '.'))
else:
    binaries.append((os.path.join(cv2_path, '*.so.*'), '.'))

# Collect missing setuptools data files
setuptools_datas, _, setuptools_hidden = collect_all('setuptools')
datas.extend(setuptools_datas)
hiddenimports.extend(setuptools_hidden)

# Also ensure jaraco.text's lorem ipsum file is included
jaraco_text_path = os.path.join(
    os.path.dirname(__import__('setuptools', fromlist=['_vendor']).__file__),
    '_vendor', 'jaraco', 'text'
)
datas.append((os.path.join(jaraco_text_path, '*.txt'), 'setuptools/_vendor/jaraco/text/'))

a = Analysis(
    ['skellycam/__main__.py'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,

)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='skellycam_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

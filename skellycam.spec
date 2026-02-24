# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
import cv2
import os

datas = []
binaries = []
hiddenimports = ["encodings.idna"]

# Collect all for cv2
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')
datas.extend(cv2_datas)
binaries.extend(cv2_binaries)
hiddenimports.extend(cv2_hiddenimports)

# cv2 submodules that collect_all sometimes misses
hiddenimports.extend([
    'cv2.cv2',
    'cv2.data',
    'cv2.aruco',
    'cv2.dnn',
    'cv2.fisheye',
    'cv2.flann',
    'cv2.img_hash',
    'cv2.optflow',
    'cv2.plot',
    'cv2.rgbd',
    'cv2.saliency',
    'cv2.stereo',
    'cv2.structured_light',
    'cv2.text',
    'cv2.videostab',
    'cv2.xfeatures2d',
    'cv2.ximgproc',
    'cv2.xphoto',
])

# Collect cv2 native libraries (handles .dll, .so, .dylib across platforms)
from PyInstaller.utils.hooks import collect_dynamic_libs
binaries.extend(collect_dynamic_libs('cv2'))

# Collect setuptools data files
setuptools_datas, _, setuptools_hidden = collect_all('setuptools')
datas.extend(setuptools_datas)
hiddenimports.extend(setuptools_hidden)

# Ensure jaraco.text lorem ipsum file is included
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
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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

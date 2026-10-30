# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules, collect_delvewheel_libs_directory
import cv2
import os

datas = []
binaries = []
hiddenimports = ["encodings.idna", "_skellycam_rust"]

# Both camera implementations ship in every installer. The Rust extension
# statically links OpenPNP; collect its Python module and native dependencies.
# PortAudio retains sounddevice's package layout so UI device indices match.
for package in ('imageio_ffmpeg', '_sounddevice_data'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hidden)

# ── OpenCV ──
# Only collect what we need from cv2 instead of collect_all which grabs
# test data, haarcascades, DNN models, and other bloat.
binaries.extend(collect_dynamic_libs('cv2'))
hiddenimports.extend(collect_submodules('cv2'))
datas, binaries = collect_delvewheel_libs_directory(
    'cv2_enumerate_cameras', datas=datas, binaries=binaries,
)

# ── setuptools (needed by some vendored deps at runtime) ──
setuptools_datas, _, setuptools_hidden = collect_all('setuptools')
datas.extend(setuptools_datas)
hiddenimports.extend(setuptools_hidden)

# Ensure jaraco.text lorem ipsum file is included
jaraco_text_path = os.path.join(
    os.path.dirname(__import__('setuptools', fromlist=['_vendor']).__file__),
    '_vendor', 'jaraco', 'text'
)
if os.path.isdir(jaraco_text_path):
    datas.append((os.path.join(jaraco_text_path, '*.txt'), 'setuptools/_vendor/jaraco/text/'))

a = Analysis(
    ['skellycam/__main__.py'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── Test frameworks ──
        'pytest',
        'pytest_asyncio',
        '_pytest',

        # ── Dev/build tools ──
        'nuitka',
        'ruff',
        'bumpver',
        'pip_tools',
        'poethepoet',
        'pyinstaller',
        'setuptools',

        # ── scipy is only used in tests ──
        'scipy',

        # ── Heavy unused stdlib/third-party modules ──
        'tkinter',
        '_tkinter',
        'matplotlib',
        'IPython',
        'notebook',
        'sphinx',
        'docutils',

        # ── Debug/profile tools ──
        'pdb',
        'cProfile',
        'profile',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='skellycam_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='skellycam_server',
)

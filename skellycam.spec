# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

datas = []
binaries = []
hiddenimports = ["encodings.idna"]

# ── OpenCV ──
# Collect only the dynamic libs and submodules from cv2 (not test data,
# haarcascades, DNN models, etc.).
binaries.extend(collect_dynamic_libs('cv2'))
hiddenimports.extend(collect_submodules('cv2'))

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

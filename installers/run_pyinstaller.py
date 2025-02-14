import logging
import os
from pathlib import Path

import PyInstaller.__main__

logger = logging.getLogger(__name__)

os.environ['PYINSTALLER_NO_CONDA'] = '1'

# SPEC_FILE_PATH = str(Path(__file__).parent / 'run_skellycam_server.spec')
# if not Path(SPEC_FILE_PATH).exists():
#     raise FileNotFoundError(f"Spec file not found at {SPEC_FILE_PATH}")
MAIN_SCRIPT_PATH = str(Path(__file__).parent.parent / 'skellycam/run_skellycam_server.py')

def run_pyinstaller():
    # print(f"Running PyInstaller with spec file {SPEC_FILE_PATH}...")

    installer_parameters = [
        # SPEC_FILE_PATH,
        '--log-level', 'INFO',
        MAIN_SCRIPT_PATH

    ]

    PyInstaller.__main__.run(installer_parameters)


if __name__ == "__main__":
    run_pyinstaller()


# usage: pyinstaller [-h] [-v] [-D] [-F] [--specpath DIR] [-n NAME]
#                    [--contents-directory CONTENTS_DIRECTORY]
#                    [--add-data SOURCE:DEST] [--add-binary SOURCE:DEST]
#                    [-p DIR] [--hidden-import MODULENAME]
#                    [--collect-submodules MODULENAME]
#                    [--collect-data MODULENAME] [--collect-binaries MODULENAME]
#                    [--collect-all MODULENAME] [--copy-metadata PACKAGENAME]
#                    [--recursive-copy-metadata PACKAGENAME]
#                    [--additional-hooks-dir HOOKSPATH]
#                    [--runtime-hook RUNTIME_HOOKS] [--exclude-module EXCLUDES]
#                    [--splash IMAGE_FILE]
#                    [-d {all,imports,bootloader,noarchive}] [--optimize LEVEL]
#                    [--python-option PYTHON_OPTION] [-s] [--noupx]
#                    [--upx-exclude FILE] [-c] [-w]
#                    [--hide-console {hide-early,hide-late,minimize-early,minimize-late}]
#                    [-i <FILE.ico or FILE.exe,ID or FILE.icns or Image or "NONE">]
#                    [--disable-windowed-traceback] [--version-file FILE]
#                    [--manifest <FILE or XML>] [-m <FILE or XML>] [-r RESOURCE]
#                    [--uac-admin] [--uac-uiaccess] [--argv-emulation]
#                    [--osx-bundle-identifier BUNDLE_IDENTIFIER]
#                    [--target-architecture ARCH] [--codesign-identity IDENTITY]
#                    [--osx-entitlements-file FILENAME] [--runtime-tmpdir PATH]
#                    [--bootloader-ignore-signals] [--distpath DIR]
#                    [--workpath WORKPATH] [-y] [--upx-dir UPX_DIR] [--clean]
#                    [--log-level LEVEL]
#                    scriptname [scriptname ...]

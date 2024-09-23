import logging
import platform
from pathlib import Path

import PyInstaller.__main__

from skellycam.__main__ import PATH_TO_SKELLYCAM_MAIN
from skellycam.system.default_paths import SKELLYCAM_SVG_PATH

OUTPUT_DIST_PATH = str(Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / 'dist')
WORK_BUILD_PATH = str(Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / 'build')

SKELLYCAM_ICON_PATH = str(
    Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / "shared" / "skellycam-logo" / "skellycam-favicon.ico")
if not Path(SKELLYCAM_ICON_PATH).exists():
    raise FileNotFoundError(f"No icon file found at location - {SKELLYCAM_ICON_PATH}")

logger = logging.getLogger(__name__)



def append_build_system_triple(base_name: str) -> str:

    try:
        logging.info('Getting platform information.')
        system = platform.system().lower()
        machine = platform.machine().lower()
        target_triple = f"{system}-{machine}"

        if not target_triple:
            logging.error(
                'Failed to determine platform target triple.')
            return

        new_name = f'{base_name}-{target_triple}'

        logging.info(f'File name with build system triple - {new_name}')
        return new_name

    except Exception as e:
        logging.error(f'An unexpected error occurred: {e}')

def run_pyinstaller():
    PyInstaller.__main__.run([
        PATH_TO_SKELLYCAM_MAIN,
        '--dist',
        OUTPUT_DIST_PATH,
        '--workpath',
        WORK_BUILD_PATH,
        '--hidden-import',
        'numpy',
        '--onefile',
        # '--clean', #clear pyinstaller cache before building if things weird out
        '--name',
        append_build_system_triple('skellycam'),
        '--icon',
        SKELLYCAM_ICON_PATH,
        '--log-level',
        'INFO'
        # '--add-data',
        # f"{SKELLYCAM_SVG_PATH };shared/skellycam-logo",
        # '--',
        # '--qt', #compile binary to use the qt gui, disable for server-only
    ])


if __name__ == "__main__":
    run_pyinstaller()

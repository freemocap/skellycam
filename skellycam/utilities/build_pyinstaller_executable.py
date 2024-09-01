import logging
import subprocess
from pathlib import Path

import PyInstaller.__main__

from skellycam.__main__ import PATH_TO_SKELLYCAM_MAIN

OUTPUT_DIST_PATH = str(Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / 'dist')
WORK_BUILD_PATH = str(Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / 'build')

SKELLYCAM_ICON_PATH = str(
    Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / "shared" / "skellycam-logo" / "skellycam-favicon.ico")
if not Path(SKELLYCAM_ICON_PATH).exists():
    raise FileNotFoundError(f"No icon file found at location - {SKELLYCAM_ICON_PATH}")

logger = logging.getLogger(__name__)


def append_build_system_triple(base_name: str) -> str:
    logging.basicConfig(level=logging.INFO)

    try:
        logging.info('Running rustc to get the target triple.')
        rust_info = subprocess.run(['rustc', '-vV'], check=True, stdout=subprocess.PIPE, text=True).stdout
        target_triple = next(line.split()[1] for line in rust_info.splitlines() if line.startswith('host:'))

        if not target_triple:
            logging.error(
                'Failed to determine platform target triple - is `rust` installed? (https://www.rust-lang.org/tools/install)')
            return

        new_name = f'{base_name}-{target_triple}'

        logging.info(f'File name with build system triple - {new_name}')
        return new_name

    except FileNotFoundError:
        logger.exception(
            "The rustc command was not found. Please ensure that Rust is installed and rustc is in your PATH (https://www.rust-lang.org/tools/install).")
    except subprocess.CalledProcessError as e:
        logging.error(f'Error occurred while running rustc: {e}')
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
        # '--clean', #clear pyinstaller cache before building
        '--name',
        append_build_system_triple('skellycam'),
        '--icon',
        SKELLYCAM_ICON_PATH

    ])


if __name__ == "__main__":
    run_pyinstaller()

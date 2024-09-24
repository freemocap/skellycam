import argparse
import logging
from pathlib import Path
import PyInstaller.__main__

logger = logging.getLogger(__name__)
PACKAGE_ROOT_PATH = Path(__file__).parent.parent

SPEC_FILE_PATH =   './skellycam.spec'
if not Path(SPEC_FILE_PATH).exists():
    raise FileNotFoundError(f"Spec file not found at {SPEC_FILE_PATH}")

def run_pyinstaller():
    print(f"Running PyInstaller with spec file {SPEC_FILE_PATH}...")

    installer_parameters = [
        SPEC_FILE_PATH,
        '--distpath', str(PACKAGE_ROOT_PATH / 'dist'),
        '--workpath', str(PACKAGE_ROOT_PATH / 'build'),
        '--log-level', 'INFO'
    ]

    PyInstaller.__main__.run(installer_parameters)


if __name__ == "__main__":
    run_pyinstaller()
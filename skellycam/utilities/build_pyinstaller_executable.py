import argparse
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


def run_pyinstaller(qt: bool = False):
    executable_base_name = 'skellycam-GUI' if qt else 'skellycam-SERVER-ONLY'
    executable_base_name = append_build_system_triple(executable_base_name)
    print(f"Running PyInstaller for {executable_base_name}...")

    # Define paths
    svg_path = Path(SKELLYCAM_SVG_PATH)
    ui_html_path = Path(PATH_TO_SKELLYCAM_MAIN).parent / "api" / "http" / "ui" / "ui.html"
    ico_path = Path(PATH_TO_SKELLYCAM_MAIN).parent.parent / "shared" / "skellycam-logo" / "skellycam-favicon.ico"

    # Check if the necessary files exist
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found at location - {svg_path}")
    if not ui_html_path.exists():
        raise FileNotFoundError(f"HTML file not found at location - {ui_html_path}")
    if not ico_path.exists():
        raise FileNotFoundError(f"ICO file not found at location - {ico_path}")

    installer_parameters = [
        PATH_TO_SKELLYCAM_MAIN,
        '--dist',
        OUTPUT_DIST_PATH,
        '--workpath',
        WORK_BUILD_PATH,
        '--hidden-import',
        'numpy',
        '--onefile',
        '--name',
        executable_base_name,
        '--icon',
        str(ico_path),
        '--log-level',
        'INFO',
        '--add-data',
        f"{svg_path};shared/skellycam-logo",
        '--add-data',
        f"{ui_html_path};skellycam/api/http/ui",
        '--add-data',
        f"{ico_path};shared/skellycam-logo",
    ]
    if qt:
        installer_parameters.extend(['--', '--qt'])

    PyInstaller.__main__.run(installer_parameters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the SkellyCam executable.")
    parser.add_argument('--qt', action='store_true', default=False, help="Build the application with a Qt GUI.")
    args = parser.parse_args()

    run_pyinstaller(qt=args.qt)
    # for qt_bool in [True, False]:
    #     run_pyinstaller(qt=qt_bool)
    #



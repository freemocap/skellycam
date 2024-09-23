import argparse
import logging
import platform
from pathlib import Path
import PyInstaller.__main__
from skellycam.__main__ import PATH_TO_SKELLYCAM_MAIN
from skellycam.system.default_paths import SKELLYCAM_SVG_PATH

logger = logging.getLogger(__name__)


class PyInstallerSetup:
    def __init__(self, qt: bool = False):
        self.qt = qt
        self.PATH_TO_SKELLYCAM_MAIN = Path(PATH_TO_SKELLYCAM_MAIN)
        self.SKELLYCAM_SVG_PATH = Path(SKELLYCAM_SVG_PATH)
        self.OUTPUT_DIST_PATH = self.PATH_TO_SKELLYCAM_MAIN.parent.parent / 'dist'
        self.WORK_BUILD_PATH = self.PATH_TO_SKELLYCAM_MAIN.parent.parent / 'build'
        self.SKELLYCAM_ICON_PATH = self.PATH_TO_SKELLYCAM_MAIN.parent.parent / "shared" / "skellycam-logo" / "skellycam-favicon.ico"
        self.ui_html_path = self.PATH_TO_SKELLYCAM_MAIN.parent / "api" / "http" / "ui" / "ui.html"

        self.check_paths()

    def check_paths(self):
        print(f"Checking paths...")
        print(f"PATH_TO_SKELLYCAM_MAIN: {self.PATH_TO_SKELLYCAM_MAIN}")
        print(f"OUTPUT_DIST_PATH: {self.OUTPUT_DIST_PATH}")
        print(f"WORK_BUILD_PATH: {self.WORK_BUILD_PATH}")
        print(f"SKELLYCAM_SVG_PATH: {self.SKELLYCAM_SVG_PATH}")
        print(f"SKELLYCAM_ICON_PATH: {self.SKELLYCAM_ICON_PATH}")
        print(f"ui_html_path: {self.ui_html_path}")

        if not self.SKELLYCAM_SVG_PATH.exists():
            raise FileNotFoundError(f"SVG file not found at location - {self.SKELLYCAM_SVG_PATH}")
        if not self.ui_html_path.exists():
            raise FileNotFoundError(f"HTML file not found at location - {self.ui_html_path}")
        if not self.SKELLYCAM_ICON_PATH.exists():
            raise FileNotFoundError(f"ICO file not found at location - {self.SKELLYCAM_ICON_PATH}")

    def append_build_system_triple(self, base_name: str) -> str:
        try:
            logging.info('Getting platform information.')
            system = platform.system().lower()
            machine = platform.machine().lower()
            target_triple = f"{system}-{machine}"

            if not target_triple:
                logging.error('Failed to determine platform target triple.')
                return

            new_name = f'{base_name}-{target_triple}'
            logging.info(f'File name with build system triple - {new_name}')
            return new_name

        except Exception as e:
            logging.error(f'An unexpected error occurred: {e}')

    def run_pyinstaller(self):
        executable_base_name = 'skellycam-GUI' if self.qt else 'skellycam-SERVER-ONLY'
        executable_base_name = self.append_build_system_triple(executable_base_name)
        print(f"Running PyInstaller for {executable_base_name}...")

        installer_parameters = [
            str(self.PATH_TO_SKELLYCAM_MAIN),
            '--dist',
            str(self.OUTPUT_DIST_PATH),
            '--workpath',
            str(self.WORK_BUILD_PATH),
            '--hidden-import',
            'numpy',
            '--onefile',
            '--name',
            executable_base_name,
            '--icon',
            str(self.SKELLYCAM_ICON_PATH),
            '--log-level',
            'INFO',
            '--add-data',
            f"{self.SKELLYCAM_SVG_PATH};shared/skellycam-logo",
            '--add-data',
            f"{self.ui_html_path};skellycam/api/http/ui",
            '--add-data',
            f"{self.SKELLYCAM_ICON_PATH};shared/skellycam-logo",
        ]
        if self.qt:
            installer_parameters.extend(['--', '--qt'])

        PyInstaller.__main__.run(installer_parameters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the SkellyCam executable.")
    parser.add_argument('--qt', action='store_true', default=False, help="Build the application with a Qt GUI.")
    args = parser.parse_args()

    setup = PyInstallerSetup(qt=args.qt)
    setup.run_pyinstaller()
    # for qt_bool in [True, False]:
    #   setup = PyInstallerSetup(qt=args.qt)
    #   setup.run_pyinstaller()




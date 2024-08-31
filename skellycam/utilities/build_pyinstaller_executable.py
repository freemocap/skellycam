import PyInstaller.__main__

from skellycam.__main__ import PATH_TO_SKELLYCAM_MAIN


def run_pyinstaller():
    PyInstaller.__main__.run([
        PATH_TO_SKELLYCAM_MAIN,
        '--onefile',
        # other pyinstaller options...
    ])

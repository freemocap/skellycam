# __main__.py
import platform
import sys
from pathlib import Path


from skellycam import qt_gui_main


def main():
    qt_gui_main()


if __name__ == "__main__":
    print(f"Running `skellycam.__main__` from - {__file__}")

    if platform.system() == "Windows":
        # set up so you can change the taskbar icon - https://stackoverflow.com/a/74531530/14662833
        import ctypes
        import skellycam
        myappid = f"{skellycam.__package_name__}_{skellycam.__version__}"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    main()

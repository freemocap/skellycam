# __main__.py
import sys
from pathlib import Path

base_package_path = Path(__file__).parent.parent
sys.path.insert(0, str(base_package_path))  # add parent d

from skellycam.qt_gui.qt_gui_main import qt_gui_main


def main():
    qt_gui_main()


if __name__ == "__main__":
    print(f"This is printing from {__file__}")
    main()

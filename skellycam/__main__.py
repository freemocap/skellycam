# __main__.py
import sys
from pathlib import Path


from skellycam.qt_gui.qt_gui_main import qt_gui_main

print(f"This is printing from {__file__}")

def main():
    qt_gui_main()


if __name__ == "__main__":
    print(f"This is printing from {__file__}")
    main()

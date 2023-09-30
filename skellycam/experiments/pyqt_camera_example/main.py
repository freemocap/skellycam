# Copyright (C) 2023 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

"""PySide6 port of the QtMultiMedia camera example from Qt v6.x"""

import sys

from PySide6.QtWidgets import QApplication

from camera_example_main_window import CameraExampleMainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = CameraExampleMainWindow()
    main_window.show()
    sys.exit(app.exec())

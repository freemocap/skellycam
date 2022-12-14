import logging
from typing import Union, List, Callable, Dict

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QPushButton

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.viewers.qt_app.qt_multi_camera_viewer_widget import QtMultiCameraViewerWidget
from fast_camera_capture.viewers.qt_app.workers.cam.camworker import (
    CamGroupFrameWorker,
)

logger = logging.getLogger(__name__)


class QtMultiCameraControllerWidget(QWidget):
    def __init__(self,
                 slot_dictionary: Dict[str, Callable] = None,
                 parent=None):
        super().__init__(parent=parent)

        self._slot_dictionary = slot_dictionary

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._button_layout, self._button_dictionary = self._create_button_dictionary()
        self._layout.addLayout(self._button_layout)

        self._connect_signals_to_slots()

    @property
    def button_dictionary(self):
        return self._button_dictionary

    def _create_button_dictionary(self):
        button_layout = QVBoxLayout()
        button_layout_top = QHBoxLayout()
        button_layout.addLayout(button_layout_top)
        button_layout_bottom = QHBoxLayout()
        button_layout.addLayout(button_layout_bottom)
        button_dictionary = {}

        pause_push_button = QPushButton("Pause")
        pause_push_button.setEnabled(False)
        button_layout_top.addWidget(pause_push_button)
        button_dictionary["pause"] = pause_push_button

        start_recording_push_button = QPushButton("Start Recording")
        button_layout_top.addWidget(start_recording_push_button)
        button_dictionary["start_recording"] = start_recording_push_button

        stop_recording_push_button = QPushButton("Stop Recording")
        stop_recording_push_button.setEnabled(False)
        button_layout_top.addWidget(stop_recording_push_button)
        button_dictionary["stop_recording"] = stop_recording_push_button


        connect_to_cameras_push_button = QPushButton("Connect to Cameras")
        button_layout_bottom.addWidget(connect_to_cameras_push_button)
        button_dictionary["connect_to_cameras"] = connect_to_cameras_push_button

        disconnect_from_cameras_push_button = QPushButton("Disconnect from Cameras")
        button_layout_bottom.addWidget(disconnect_from_cameras_push_button)
        button_dictionary["disconnect_from_cameras"] = disconnect_from_cameras_push_button

        return button_layout, button_dictionary

    def _connect_signals_to_slots(self):
        for button_name, button in self._button_dictionary.items():
            if button_name in self._slot_dictionary:
                button.clicked.connect(self._slot_dictionary[button_name])
            else:
                logger.warning(f"No slot found for button: {button_name} in slot dictionary: {self._slot_dictionary}")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    qt_multi_camera_controller_widget = QtMultiCameraControllerWidget()
    main_window.setCentralWidget(qt_multi_camera_controller_widget)
    main_window.show()
    error_code = app.exec()
    qt_multi_camera_viewer_widget.close()

    sys.exit()

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class QMLCamera(QWidget):
    def __init__(self):
        super().__init__()

        # QQuickWidget for embedding QML
        self.qml_widget = QQuickWidget()
        camera_view_qml_path = str(Path(__file__).parent / "single_camera.qml")
        self.qml_widget.setSource(QUrl.fromLocalFile(camera_view_qml_path))
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

        # Embed QML in QWidget
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.qml_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = QMLCamera()
    widget.show()

    sys.exit(app.exec())

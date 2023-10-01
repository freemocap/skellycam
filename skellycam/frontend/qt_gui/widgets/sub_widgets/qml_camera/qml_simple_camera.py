import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Slot
from PySide6.QtQml import QQmlError
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import logging


logger = logging.getLogger(__name__)

class QMLCamera(QWidget):
    def __init__(self):
        super().__init__()

        # QQuickWidget for embedding QML
        self.qml_widget = QQuickWidget()
        self.qml_widget.engine().addImportPath(str(Path(__file__).parent / 'components'))
        camera_view_qml_path = str(Path(__file__).parent / "camera_view.qml")
        self.qml_widget.setSource(QUrl.fromLocalFile(camera_view_qml_path))
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)


        # Embed QML in QWidget
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.qml_widget)

    @Slot(QQmlError)
    def handle_qml_errors(self, error):
        logger.info(error.toString())


if __name__ == "__main__":
    from skellycam.frontend.qt_gui.widgets.sub_widgets.qml_camera.components.qml_resources_qrc import qInitResources
    qInitResources()
    app = QApplication(sys.argv)

    widget = QMLCamera()
    widget.show()

    sys.exit(app.exec())

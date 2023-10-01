import sys

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()

    # QQuickWidget for embedding QML
    qml_widget = QQuickWidget()
    qml_widget.setSource(QUrl('declarative-camera.qml'))
    qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

    # Embed QML in QWidget
    main_widget = QWidget()
    main_widget.setLayout(QVBoxLayout())
    main_widget.layout().addWidget(qml_widget)

    # Set the widget as the central widget of the QMainWindow
    window.setCentralWidget(main_widget)
    window.show()

    sys.exit(app.exec())

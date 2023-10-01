from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QVBoxLayout, QApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QWidget


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.view = QQuickView()
        self.container = QWidget.createWindowContainer(self.view, self)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.container)

        self.view.setSource(QUrl.fromLocalFile('camera.qml'))

        self.show()

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
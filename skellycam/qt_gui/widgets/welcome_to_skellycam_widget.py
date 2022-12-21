from PyQt6.QtWidgets import QWidget


class WelcomeToSkellyCamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to SkellyCam!")
        self.setGeometry(300, 300, 300, 200)
        self.show()


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    ex = WelcomeToSkellyCamWidget()
    sys.exit(app.exec())



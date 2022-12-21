from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from skellycam.system.environment.default_paths import PATH_TO_SKELLY_CAM_LOGO


class WelcomeToSkellyCamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        skellycam_logo_label = QLabel(self)
        skellycam_logo_pixmap = QPixmap(PATH_TO_SKELLY_CAM_LOGO)
        skellycam_logo_label.setPixmap(skellycam_logo_pixmap)
        self._layout.addWidget(skellycam_logo_label)

        skellycam_text_label = QLabel(self)
        skellycam_text_label.setText("Welcome to Skelly Cam \U0001F480 \U0001F4F8")
        self._layout.addWidget(skellycam_text_label)

        self.resize(skellycam_logo_pixmap.width(), skellycam_logo_pixmap.height())





if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
    welcome_to_skellycam_widget.show()
    sys.exit(app.exec())



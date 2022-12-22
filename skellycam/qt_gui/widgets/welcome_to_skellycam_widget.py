from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from skellycam.system.environment.default_paths import PATH_TO_SKELLY_CAM_LOGO_SVG


class WelcomeToSkellyCamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        skellycam_logo_label = QLabel(self)
        self._layout.addWidget(skellycam_logo_label)

        skellycam_logo_pixmap = QPixmap(PATH_TO_SKELLY_CAM_LOGO_SVG)
        skellycam_logo_pixmap = skellycam_logo_pixmap.scaledToWidth(300)
        skellycam_logo_label.setPixmap(skellycam_logo_pixmap)
        skellycam_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        skellycam_text_label = QLabel(self)
        self._layout.addWidget(skellycam_text_label)

        skellycam_text_label.setText("Welcome to Skelly Cam!")
        skellycam_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skellycam_text_label.setStyleSheet("""
                                            font-size: 54px;
                                           font-family: 'Dosis', sans-serif;
                                           color: #1b1e28;
                                            """)



        self.resize(skellycam_logo_pixmap.width(), skellycam_logo_pixmap.height())


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
    welcome_to_skellycam_widget.show()
    sys.exit(app.exec())

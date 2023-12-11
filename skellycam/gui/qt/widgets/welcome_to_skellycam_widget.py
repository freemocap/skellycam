from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

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

        subtitle_text_label = QLabel(self)
        self._layout.addWidget(subtitle_text_label)

        subtitle_text_label.setText("The camera back-end for the FreeMoCap Project \U00002728")
        subtitle_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_text_label.setStyleSheet("""
                                            font-size: 24px;
                                           font-family: 'Dosis', sans-serif;
                                           color: #2b2e38;
                                            """)

        self.resize(skellycam_logo_pixmap.width(), skellycam_logo_pixmap.height())


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
    welcome_to_skellycam_widget.show()
    sys.exit(app.exec())

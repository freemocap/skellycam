from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts Help")
        layout = QVBoxLayout()

        # Create a label to show the shortcuts
        shortcuts_text = (
            "Keyboard Shortcuts:\n"
            "0-9: Emits the respective number\n"
            "A: Annotate images\n"
            "W/Up Arrow: Increase camera exposure\n"
            "S/Down Arrow: Decrease camera exposure\n"
            "C: Connect to cameras\n"
            "R: Start/Stop recording\n"
            "Spacebar: Pause\n"
            "Ctrl+Space: Take snapshot\n"
            "H: Show this help"
        )
        label = QLabel(shortcuts_text)
        layout.addWidget(label)

        # Add a close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        self.setLayout(layout)
class KeyboardShortcuts(QObject):
    number_pressed = Signal(int)
    annotate_images = Signal()
    increase_exposure = Signal()
    decrease_exposure = Signal()
    connect_cameras = Signal()
    toggle_recording = Signal()
    pause = Signal()
    take_snapshot = Signal()
    show_help = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Shortcuts for numbers 0-9
        for i in range(10):
            shortcut = QShortcut(QKeySequence(str(i)), parent)
            shortcut.activated.connect(lambda i=i: self.number_pressed.emit(i))

        # Shortcut for 'a' - Annotate images
        QShortcut(QKeySequence("A"), parent).activated.connect(self.annotate_images.emit)

        # Shortcuts for 'w' or 'Up Arrow' - Increase camera exposure
        QShortcut(QKeySequence("W"), parent).activated.connect(self.increase_exposure.emit)
        QShortcut(QKeySequence("Up"), parent).activated.connect(self.increase_exposure.emit)

        # Shortcuts for 's' or 'Down Arrow' - Decrease camera exposure
        QShortcut(QKeySequence("S"), parent).activated.connect(self.decrease_exposure.emit)
        QShortcut(QKeySequence("Down"), parent).activated.connect(self.decrease_exposure.emit)

        # Shortcut for 'c' - Connect to cameras
        QShortcut(QKeySequence("C"), parent).activated.connect(self.connect_cameras.emit)

        # Shortcut for 'r' - Start/Stop recording
        QShortcut(QKeySequence("R"), parent).activated.connect(self.toggle_recording.emit)

        # Shortcut for 'Spacebar' - Pause
        QShortcut(QKeySequence("Space"), parent).activated.connect(self.pause.emit)

        # Shortcut for 'Ctrl+Space' - Take snapshot
        QShortcut(QKeySequence("Ctrl+Space"), parent).activated.connect(self.take_snapshot.emit)

        # Shortcut for 'h' - Show help
        QShortcut(QKeySequence("H"), parent).activated.connect(lambda: HelpDialog(parent).show())

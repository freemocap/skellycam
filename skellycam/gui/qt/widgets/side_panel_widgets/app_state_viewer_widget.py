from PySide6.QtWidgets import QWidget, QTextEdit, QVBoxLayout


class AppStateJsonViewer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("App State (JSON)")

        # Create a QTextEdit widget
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("{}")
        self.text_edit.setReadOnly(True)  # Make the text area read-only

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def update_text(self, new_text: str) -> None:
        """
        Update the text displayed in the QTextEdit widget.

        Parameters
        ----------
        new_text : str
            The new text to display.
        """
        # Save the current scroll position
        vertical_scroll_pos = self.text_edit.verticalScrollBar().value()
        horizontal_scroll_pos = self.text_edit.horizontalScrollBar().value()

        # Update the text
        self.text_edit.setText(f"WARNING: MAY NOT BE ACCURATE.\n{new_text}")

        # Restore the scroll position
        self.text_edit.verticalScrollBar().setValue(vertical_scroll_pos)
        self.text_edit.horizontalScrollBar().setValue(horizontal_scroll_pos)

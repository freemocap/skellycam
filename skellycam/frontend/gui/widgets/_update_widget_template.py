from copy import deepcopy
from typing import Union

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QMainWindow

from skellycam import logger
from skellycam.data_models.request_response_update import UpdateModel, BaseMessage


class UpdateWidget(QWidget):
    """
    Widget that emits an 'updated' signal when data changes.

    This signal can be a dictionary or an instance of the UpdateModel
    class. Any other type of data will cause a TypeError. The signal
    is sent to a designated parent widget.

    Attributes:
        updated (Signal): Emitted when an update occurs.
    """

    updated = Signal(UpdateModel)

    def __init__(self, parent: Union[QMainWindow, 'UpdateWidget', QWidget], *args, **kwargs):
        """
        Args:
            parent (UpdateWidget): The parent widget that this widget sends update signals to - makes a tree and trees are cool :D
        """
        self._get_route(parent)
        logger.trace(f"Initializing {self.name}...")
        super().__init__(*args, **kwargs)
        self.updated.connect(parent.emit_message)

    def _get_route(self, parent):
        if isinstance(parent, QMainWindow):
            self._route = ["MainWindow"]
        else:
            self._route = deepcopy(parent.route)
        self._route.append(self.__class__.__name__)

    @property
    def route(self) -> list[str]:
        return self._route

    @property
    def name(self):
        """
        Returns the name of the widget, which looks like this:
        "main_window.camera_grid.camera_widget"
        """
        name = ".".join(self._route)
        return name

    def emit_message(self, message: BaseMessage) -> None:
        logger.trace(f"Emitting update signal with data: \n{message}")
        self.updated.emit(message)

    def update_view(self, message: BaseMessage):
        raise NotImplementedError

from typing import Union

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from skellycam import logger
from skellycam.data_models.request_response import UpdateModel


class UpdateWidget(QWidget):
    updated = Signal(dict)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def emit_update(self, data: Union[dict, UpdateModel]) -> None:
        if isinstance(data, dict):
            UpdateModel(source=self.__class__.__name__,
                        data=data)
            logger.trace(f"Emitting update signal with data: {data}")
        elif isinstance(data, UpdateModel):
            logger.trace(f"Passing along update signal with data: {data}")
        else:
            raise TypeError(f"Expected data to be of type dict or UpdateModel, but got type {type(data)}")

        self.updated.emit(data)

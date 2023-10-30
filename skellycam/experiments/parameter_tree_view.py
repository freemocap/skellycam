from abc import ABC, abstractmethod

from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QTreeView
from pydantic import BaseModel

from skellycam.models.cameras.camera_config import CameraConfig


class ParameterTreeView(QTreeView):
    """
    A QTreeView that displays a pydantic model
    """
    def __init__(self, model: BaseModel):
        super(ParameterTreeView, self).__init__()
        self.standard_model = QStandardItemModel()
        self.setModel(self.standard_model)
        self.model = model
        self.build_tree()

    def build_tree(self):
        for field_name, field_value in self.model.dict().items():
            if isinstance(field_value, BaseModel):
                child = self.__class__(field_value)
                parent = QStandardItem(field_name)
                parent.appendRow(child)
                self.standard_model.appendRow(parent)
                continue
            parent = QStandardItem(field_name)
            child = QStandardItem(str(field_value))
            parent.appendRow(child)
            self.standard_model.appendRow(parent)

    @abstractmethod
    def update_model(self, new_model: BaseModel):
        pass

    @abstractmethod
    def extract_model(self) -> BaseModel:
        pass


class CameraConfigView(ParameterTreeView):
    def __init__(self, model: CameraConfig):
        super(CameraConfigView, self).__init__(model)

    def update_model(self, new_model: CameraConfig):
        self.model = new_model
        self.build_tree()

    def extract_model(self) -> CameraConfig:
        model_dict = {}
        for index in range(self.standard_model.rowCount()):
            parent = self.standard_model.item(index)
            field_name = parent.text()
            field_value = parent.child(0).text()
            model_dict[field_name] = type(self.model.__fields__[field_name].outer_type_)(field_value)
        return CameraConfig(**model_dict)


if __name__ == "__main__":
    # A simple example of how to use the ParameterTree class
    # to display a pydantic model in a QTreeView
    # and then extract the model from the tree

    from PySide6.QtWidgets import QApplication
    from pprint import pprint
    import sys

    app = QApplication(sys.argv)

    input_model = CameraConfig(camera_id='0')
    pprint(f"Input model:\n\n {input_model}\n", indent=4)

    model = CameraConfigView(model=input_model)
    model.show()

    app.exec()

    extracted_model = model.extract_model()

    pprint(extracted_model, indent=4)

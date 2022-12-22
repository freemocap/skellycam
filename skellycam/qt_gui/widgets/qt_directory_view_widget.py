import logging
import os
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QLabel, QMenu, QTreeView, QVBoxLayout, QWidget
from qtpy import QtGui

logger = logging.getLogger(__name__)


class QtDirectoryViewWidget(QWidget):
    def __init__(self, folder_path: Union[str, Path] = None):
        logger.info("Creating QtDirectoryViewWidget")
        super().__init__()
        self._minimum_width = 300
        self.setMinimumWidth(self._minimum_width)
        self._folder_path = folder_path

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._path_label = QLabel(str(self._folder_path))
        self._layout.addWidget(self._path_label)
        self._file_system_model = QFileSystemModel()
        self._tree_view_widget = QTreeView()



        self._layout.addWidget(self._tree_view_widget)

        # self._tree_view_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view_widget.customContextMenuRequested.connect(self._context_menu)
        self._tree_view_widget.doubleClicked.connect(self.open_file)

        self._tree_view_widget.setModel(self._file_system_model)

        self._tree_view_widget.setAlternatingRowColors(True)
        self._tree_view_widget.resizeColumnToContents(1)

        if self._folder_path is not None:
            self.set_folder_as_root(self._folder_path)

    def set_folder_as_root(self, folder_path: Union[str, Path]):
        logger.info(f"Setting root folder to {str(folder_path)}")
        self._tree_view_widget.setWindowTitle(str(folder_path))
        self._file_system_model.setRootPath(str(folder_path))
        self._tree_view_widget.setRootIndex(
            self._file_system_model.index(str(folder_path))
        )
        self._tree_view_widget.setColumnWidth(0, int(self._minimum_width * 0.9))

    def _context_menu(self):
        menu = QMenu()
        open = menu.addAction("Open file")
        open.triggered.connect(self.open_file)
        load_session = menu.addAction("Load session folder")
        load_session.triggered.connect(self.load_session_folder)

        cursor = QtGui.QCursor()
        menu.exec_(cursor.pos())

    def open_file(self):
        index = self._tree_view_widget.currentIndex()
        file_path = self._file_system_model.filePath(index)
        logger.info(f"Opening file from file_system_view_widget: {file_path}")
        os.startfile(file_path)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    qt_directory_view_widget = QtDirectoryViewWidget(folder_path=Path.home())

    qt_directory_view_widget.show()
    sys.exit(app.exec())

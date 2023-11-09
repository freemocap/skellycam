import multiprocessing
from typing import Optional

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTabWidget

from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.camera_views.camera_grid import CameraGrid
from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.record_buttons import RecordButtons
from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.welcome import Welcome
from skellycam.frontend.gui.skellycam_widget.sub_widgets.side_panel_widgets.camera_control_buttons import \
    CameraControlButtons
from skellycam.frontend.gui.skellycam_widget.sub_widgets.side_panel_widgets.camera_parameter_tree import \
    CameraParameterTree
from skellycam.frontend.gui.skellycam_widget.sub_widgets.side_panel_widgets.directory_view import DirectoryView
from skellycam.frontend.manager.skellycam_manager import SkellycamManager
from skellycam.system.environment.default_paths import (get_default_skellycam_base_folder_path)
from skellycam.system.environment.get_logger import logger


class SkellyCamWidget(QWidget):

    def __init__(self,
                 messages_from_frontend: multiprocessing.Queue = None,
                 messages_from_backend: multiprocessing.Queue = None,
                 frontend_frame_pipe_receiver=None,  # multiprocessing.connection.Connection,
                 parent: Optional[QWidget] = None,
                 exit_event: multiprocessing.Event = None,
                 ):
        super().__init__(parent=parent)
        self._parent = parent
        self._initUI()
        self._exit_event = exit_event if exit_event is not None else multiprocessing.Event()

        if self._parent is not None:
            self._parent.destroyed.connect(self.close)

        self._manager = SkellycamManager(main_widget=self,
                                         exit_event=self._exit_event,
                                         messages_from_frontend=messages_from_frontend,
                                         messages_from_backend=messages_from_backend,
                                         frontend_frame_pipe_receiver=frontend_frame_pipe_receiver)

    def _initUI(self):
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._central_layout = QVBoxLayout()
        self._layout.addLayout(self._central_layout)

        self.welcome = Welcome(parent=self)
        self._central_layout.addWidget(self.welcome)
        self.camera_grid = CameraGrid(parent=self)
        self.camera_grid.resize(1280, 720)
        self.record_buttons = RecordButtons(parent=self, )
        self._central_layout.addWidget(self.record_buttons)
        self._central_layout.addWidget(self.camera_grid)
        self.camera_grid.hide()
        self.record_buttons.hide()

        self.side_panel = self._create_side_panel()
        self.side_panel.hide()
        self._layout.addWidget(self.side_panel)

    def _create_side_panel(self) -> QTabWidget:
        tab_widget = QTabWidget()
        tab_widget.setTabPosition(QTabWidget.TabPosition.East)

        self.camera_settings_panel = self._create_camera_settings_tab()
        tab_widget.addTab(self.camera_settings_panel, "Camera Settings")

        tab_widget.setFixedWidth(300)
        self.directory_view = DirectoryView(folder_path=get_default_skellycam_base_folder_path())
        tab_widget.addTab(self.directory_view, "Directory View")

        return tab_widget

    def _create_camera_settings_tab(self) -> QWidget:
        self.camera_settings_panel = QWidget(parent=self)
        camera_settings_layout = QVBoxLayout()
        self.camera_settings_panel.setLayout(camera_settings_layout)

        self.camera_control_buttons = CameraControlButtons(parent=self)
        camera_settings_layout.addWidget(self.camera_control_buttons)

        self.camera_parameter_tree = CameraParameterTree(parent=self)
        camera_settings_layout.addWidget(self.camera_parameter_tree)
        camera_settings_widget = QWidget(parent=self)
        camera_settings_widget.setLayout(camera_settings_layout)
        return camera_settings_widget

    def _set_exit_event(self):
        logger.info("SETTING EXIT EVENT")
        self._exit_event.set()

    def close(self):
        logger.info("Closing SkellyCamWidget...")
        self._set_exit_event()
        super().close()

if __name__ == '__main__':
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = SkellyCamWidget()
    widget.show()
    sys.exit(app.exec())

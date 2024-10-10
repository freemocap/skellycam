import logging
from typing import Dict, List

from PySide6.QtCore import QMutex, QMutexLocker
from PySide6.QtWidgets import QWidget, QHBoxLayout, QGridLayout, QVBoxLayout

from skellycam.core import CameraId
from skellycam.gui.qt.gui_state.gui_state import GUIState, get_gui_state
from skellycam.gui.qt.gui_state.models.camera_framerate_stats import CameraFramerateStats
from skellycam.gui.qt.gui_state.models.camera_view_sizes import CameraViewSizes
from skellycam.gui.qt.widgets.camera_views.single_camera_view import SingleCameraViewWidget

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 2
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 5

logger = logging.getLogger(__name__)


class CameraViewGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_grids_layout = QHBoxLayout()
        self._layout.addLayout(self._camera_grids_layout)

        self._camera_landscape_grid_layout = QGridLayout()
        self._camera_grids_layout.addLayout(self._camera_landscape_grid_layout)

        self._camera_portrait_grid_layout = QGridLayout()
        self._camera_grids_layout.addLayout(self._camera_portrait_grid_layout)

        self.setStyleSheet("""
                            font-size: 12px;
                            font-weight: bold;
                            font-family: "Dosis", sans-serif;
        """)
        self._single_camera_views: Dict[CameraId, SingleCameraViewWidget] = {}
        self._gui_state: GUIState = get_gui_state()
        self._gui_state.set_image_update_callable(self.set_image_data)

        self._mutex_lock = QMutex()

    @property
    def single_camera_view_camera_ids(self) -> List[CameraId]:
        if self._single_camera_views:
            return list(self._single_camera_views.keys())
        return []

    @property
    def camera_view_sizes(self) -> CameraViewSizes:
        with QMutexLocker(self._mutex_lock):
            return CameraViewSizes(
                sizes={camera_id: {"width": view.image_size.width(), "height": view.image_size.height()}
                       for camera_id, view in self._single_camera_views.items()})

    @property
    def grid_empty(self) -> bool:
        return len(self._single_camera_views) == 0

    def update_widget(self):
        if self._gui_state.connected_camera_ids != self.single_camera_view_camera_ids:
            self.clear_camera_views()
            self.create_single_camera_views()

    def set_image_data(self,
                       jpeg_images: Dict[CameraId, str],
                       framerate_stats_by_camera: Dict[CameraId, CameraFramerateStats],
                       recording_in_progress: bool = False):
        with QMutexLocker(self._mutex_lock):
            for camera_id, single_camera_view in self._single_camera_views.items():
                single_camera_view.update_image(base64_str=jpeg_images[camera_id],
                                                framerate_stats=None,
                                                recording=recording_in_progress)

    def create_single_camera_views(self):
        if not self._gui_state.connected_camera_configs:
            return
        landscape_camera_number = -1
        portrait_camera_number = -1
        for camera_id, camera_config in self._gui_state.connected_camera_configs.items():

            single_camera_view = SingleCameraViewWidget(camera_id=camera_id,
                                                        camera_config=camera_config,
                                                        parent=self)

            if camera_config.orientation == "landscape" or "square":
                landscape_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(landscape_camera_number),
                                                        MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_landscape_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            elif camera_config.orientation == "portrait":
                portrait_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(portrait_camera_number),
                                                        MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_portrait_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            self._single_camera_views[camera_id] = single_camera_view

    def clear_camera_views(self):
        if self.grid_empty:
            return
        with QMutexLocker(self._mutex_lock):
            logger.gui("Clearing camera layout dictionary")
            try:
                for camera_id, single_camera_view in self._single_camera_views.items():
                    single_camera_view.close()
                    self._camera_portrait_grid_layout.removeWidget(single_camera_view)
                    self._camera_landscape_grid_layout.removeWidget(single_camera_view)
                    single_camera_view.deleteLater()
                self._single_camera_views = {}
            except Exception as e:
                logger.exception(f"Error clearing camera layout dictionary: {e}")
                raise

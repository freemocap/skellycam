import logging
from typing import Dict

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QHBoxLayout, QGridLayout, QVBoxLayout

from skellycam.core import CameraId
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.gui.gui_state import GUIState, get_gui_state
from skellycam.gui.qt.widgets.single_camera_view import SingleCameraViewWidget

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
        self._gui_state.set_image_update_callable(self.handle_new_frontend_payload)

    @Slot()
    def create_single_camera_views(self):
        logger.debug("Updating camera views")

        landscape_camera_number = -1
        portrait_camera_number = -1
        for camera_id, camera_config in self._gui_state.camera_configs.items():

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
        if len(self._single_camera_views) == 0:
            return

        logger.debug("Clearing camera layout dictionary")
        try:
            for camera_id, single_camera_view in self._single_camera_views.items():
                single_camera_view.close()
                self._camera_portrait_grid_layout.removeWidget(single_camera_view)
                self._camera_landscape_grid_layout.removeWidget(single_camera_view)
        except Exception as e:
            logger.error(f"Error clearing camera layout dictionary: {e}")
            raise e

    def handle_new_frontend_payload(self, frontend_frame_payload: FrontendFramePayload):
        for camera_id, single_camera_view in self._single_camera_views.items():
            single_camera_view.update_image(frontend_frame_payload.jpeg_images[camera_id])

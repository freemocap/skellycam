import logging
from typing import Dict, List

from PySide6.QtCore import Slot, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QGridLayout, QVBoxLayout

from skellycam.core import CameraId
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.qt_gui.qt.widgets.camera_widgets.single_camera_view import SingleCameraViewWidget

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 3
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 5

logger = logging.getLogger(__name__)


class CameraViewGrid(QWidget):
    camera_selected = Signal(CameraId)

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
        self._selected_camera_id: CameraId | None = None
        self.setup_click_signals()
        self._latest_frontend_payload: FrontendFramePayload | None = None


    def toggle_annotation(self):
        for single_camera_view in self._single_camera_views.values():
            single_camera_view.annotate_images = not single_camera_view.annotate_images
    def setup_click_signals(self):
        for camera_id, single_camera_view in self._single_camera_views.items():
            single_camera_view.clicked.connect(lambda cid=camera_id: self.select_camera(cid))

    def select_camera(self, selected_camera_id: CameraId):
        for camera_id, single_camera_view in self._single_camera_views.items():
            if camera_id == selected_camera_id:
                single_camera_view.toggle_selected()

        self.camera_selected.emit(selected_camera_id)


    @property
    def single_camera_view_camera_ids(self) -> List[CameraId]:
        if self._single_camera_views:
            return list(self._single_camera_views.keys())
        return []


    @property
    def grid_empty(self) -> bool:
        return len(self._single_camera_views) == 0

    def update_single_camera_view_widgets(self, frontend_payload:FrontendFramePayload):
        self.clear_camera_views()
        self.create_single_camera_views(frontend_payload)

    @Slot(object)
    def handle_new_frontend_payload(self,
                                    frontend_payload:FrontendFramePayload):
        logger.gui(f"Updating {self.__class__.__name__} with {len(frontend_payload.jpeg_images)} images")
        if not list(self._single_camera_views.keys()) == frontend_payload.camera_ids:
            logger.gui(f"Updating single camera view widgets to match frontend payload ids: {frontend_payload.camera_ids}")
            self.update_single_camera_view_widgets(frontend_payload)
        for camera_id, single_camera_view in self._single_camera_views.items():
            single_camera_view.update_image(base64_str=frontend_payload.jpeg_images[camera_id])

    def create_single_camera_views(self, frontend_payload: FrontendFramePayload):
        self._latest_frontend_payload = frontend_payload
        landscape_camera_number = -1
        portrait_camera_number = -1
        total_landscape_cameras = sum(
            1 for config in frontend_payload.camera_configs.values() if config.orientation in ["landscape", "square"]
        )

        max_rows_for_landscape = 2 if total_landscape_cameras <= 4 else 3
        max_columns_for_landscape = 2 if total_landscape_cameras <= 4 else 3

        for camera_id, camera_config in frontend_payload.camera_configs.items():
            single_camera_view = SingleCameraViewWidget(camera_id=camera_id,
                                                        get_camera_config=lambda: self._latest_frontend_payload.camera_configs[camera_id],
                                                        parent=self)

            if camera_config.orientation in ["landscape", "square"]:
                landscape_camera_number += 1
                divmod_whole, divmod_remainder = divmod(landscape_camera_number, max_columns_for_landscape)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_landscape_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            elif camera_config.orientation == "portrait":
                portrait_camera_number += 1
                divmod_whole, divmod_remainder = divmod(portrait_camera_number,
                                                        MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_portrait_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            self._single_camera_views[camera_id] = single_camera_view

    def clear_camera_views(self):
        if self.grid_empty:
            return
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

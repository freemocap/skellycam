import asyncio
import multiprocessing
from typing import List

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.experiments.cam_show import cam_show
from fast_camera_capture.opencv.group.strategies.grouped_process_strategy import \
    GroupedProcessStrategy
from fast_camera_capture.opencv.group.strategies.strategies import Strategy


class CameraGroup:
    def __init__(self, cam_ids: List[str], strategy: Strategy = Strategy.X_CAM_PER_PROCESS):
        self._strategy_enum = strategy
        self._cam_ids = cam_ids
        # Make optional, if a list of cams is sent then just use that
        if not cam_ids:
            _cams = detect_cameras()
            cam_ids = _cams.cameras_found_list
        self._strategy_class = self._resolve_strategy(cam_ids)

    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def exit_event(self):
        return self._exit_event

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        self._exit_event = multiprocessing.Event()
        self._strategy_class.start_capture(self.exit_event)



    def get_by_cam_id(self, cam_id: str):
        return self._strategy_class.get_by_cam_id(cam_id)

    def latest_frames(self):
        return self._strategy_class.get_latest_frames()

    def _resolve_strategy(self, cam_ids: List[str]):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(cam_ids)


async def getall(g: CameraGroup):
    await asyncio.gather(
        cam_show("0", lambda: g.get_by_cam_id("0")),
        cam_show("2", lambda: g.get_by_cam_id("2"))
    )


if __name__ == "__main__":
    cams = ["0"]
    g = CameraGroup(cams)
    g.start()

    asyncio.run(getall(g))

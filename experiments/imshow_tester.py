import asyncio

from skellycam.core import Camera
from skellycam.core import detect_cameras
from skellycam.core.cameras.camera.config.camera_config import CameraConfig


async def imshow_testing():
    cams = detect_cameras()
    cvcams = []
    for info in cams.cameras_found_list:
        c = Camera(CameraConfig(camera_id=info))
        c.connect()
        cvcams.append(c)

    await asyncio.gather(*[cam.show_async() for cam in cvcams])


if __name__ == "__main__":
    asyncio.run(imshow_testing())

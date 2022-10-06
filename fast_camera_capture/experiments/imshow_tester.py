import asyncio

from fast_camera_capture.opencv.camera.models.cam_args import CamArgs
from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.opencv.camera.camera import Camera


async def imshow_testing():
    cams = detect_cameras()
    cvcams = []
    for info in cams.cameras_found_list:
        c = Camera(CamArgs(cam_id=info))
        c.connect()
        cvcams.append(c)

    await asyncio.gather(*[cam.show_async() for cam in cvcams])


if __name__ == "__main__":
    asyncio.run(imshow_testing())

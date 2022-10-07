import asyncio

from fast_camera_capture.opencv.viewer.cv_cam_viewer import CvCamViewer


async def cam_show(cam_id, get_frame):
    viewer = CvCamViewer()
    viewer.begin_viewer(cam_id)
    while True:
        viewer.recv_img(get_frame())
        await asyncio.sleep(0)

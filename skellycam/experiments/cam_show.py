import asyncio

from skellycam.viewers.cv_cam_viewer import CvCamViewer


async def cam_show(cam_id, get_frame):
    viewer = CvCamViewer()
    viewer.begin_viewer(cam_id)
    while True:
        viewer.recv_img(get_frame())
        await asyncio.sleep(0)

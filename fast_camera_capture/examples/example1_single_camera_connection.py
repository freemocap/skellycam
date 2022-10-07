from fast_camera_capture import CamArgs, Camera

if __name__ == "__main__":
    cam1 = Camera(CamArgs(cam_id=0))
    cam1.connect()
    cam1.show()

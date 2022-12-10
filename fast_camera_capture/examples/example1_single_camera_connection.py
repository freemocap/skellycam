from fast_camera_capture import WebcamConfig, Camera

if __name__ == "__main__":
    cam1 = Camera(WebcamConfig(cam_id=0))
    cam1.connect()
    cam1.show()

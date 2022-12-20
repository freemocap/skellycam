from skellycam import Camera, CameraConfig

if __name__ == "__main__":
    cam1 = Camera(CameraConfig(camera_id=0))
    cam1.connect()
    cam1.show()

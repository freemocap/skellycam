from skellycam.experiments import MultiCameraVideoRecorder

if __name__ == "__main__":
    """
    Connects to every available (opencv compatible) USB camera and applies a default configuration (if not specified by a dictionary of the form {camera_id: CameraConfig}.
    Displays camera views in opencv `cv2.imshow` windows.
    Records synchronized videos (as `.mp4` files) to a session folder in the default video save path (`[users_home_directory]/skelly-cam-recordings`).

    Also creates diagnostic plots to ensure synchronization and a `session_information.json` file

    """
    synchronized_video_recorder = MultiCameraVideoRecorder()
    synchronized_video_recorder.run()

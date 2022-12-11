from fast_camera_capture import SynchronizedVideoRecorder

if __name__ == "__main__":
    """
    Connects to every available (opencv compatible) USB camera ans  
    records synchronized videos (as `.mp4` files) to a folder.
    Also creates diagnostic plots to ensure synchronization and a `session_information.json` file.
    """
    synchronized_video_recorder = SynchronizedVideoRecorder()
    synchronized_video_recorder.run()

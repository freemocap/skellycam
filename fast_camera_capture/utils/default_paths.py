import time
from pathlib import Path

DEFAULT_VIDEO_FOLDER_NAME = "fast-camera-capture-recordings"


def default_video_save_path():
    return Path.home() / DEFAULT_VIDEO_FOLDER_NAME


def default_session_name():
    return time.strftime("%m-%d-%Y_%H_%M_%S")

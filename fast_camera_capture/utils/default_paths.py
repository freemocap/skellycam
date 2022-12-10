import time
from pathlib import Path

DEFAULT_VIDEO_FOLDER_NAME = "fast-camera-capture-recordings"


def default_video_save_path():
    return Path.home() / DEFAULT_VIDEO_FOLDER_NAME


def default_session_name(string_tag: str = None):
    if string_tag is not None:
        string_tag = f"_{string_tag}"
    else:
        string_tag = ""
    return time.strftime("%m-%d-%Y_%H_%M_%S" + string_tag)

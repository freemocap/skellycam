import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Union

import skellycam
from skellycam.system.environment.home_dir import os_independent_home_dir

logger = logging.getLogger(__name__)

DEFAULT_SKELLYCAM_BASE_FOLDER_NAME = "skelly-cam-recordings"
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
LOGS_INFO_AND_SETTINGS_FOLDER_NAME = "logs_info_and_settings"
LOG_FILE_FOLDER_NAME = "logs"
TIMESTAMPS_FOLDER_NAME = "timestamps"

#Emoji strings
RED_X_EMOJI_STRING = "\U0000274C"
MAGNIFYING_GLASS_EMOJI_STRING = "\U0001F50D"
CAMERA_WITH_FLASH_EMOJI_STRING = "\U0001F4F8"
HAMMER_AND_WRENCH_EMOJI_STRING = "\U0001F6E0"


SESSION_START_TIME_FORMAT_STRING = "ISO6201 format timestamp with GMT offset in hours"

PATH_TO_SKELLY_CAM_LOGO_SVG = str(
    Path(skellycam.__file__).parent.parent / "assets/logo/skelly-cam-logo.svg"
)


def get_default_skellycam_base_folder_path():
    return Path(os_independent_home_dir()) / DEFAULT_SKELLYCAM_BASE_FOLDER_NAME


def get_default_session_folder_path(create_folder: bool = True, string_tag: str = None):
    folder_path = get_default_skellycam_base_folder_path() / default_session_name(string_tag=string_tag)
    if create_folder:
        folder_path.mkdir(parents=True, exist_ok=True)
    return str(folder_path)


def get_log_file_path():
    log_folder_path = (
            Path(get_default_skellycam_base_folder_path())
            / LOGS_INFO_AND_SETTINGS_FOLDER_NAME
            / LOG_FILE_FOLDER_NAME
    )
    log_folder_path.mkdir(exist_ok=True, parents=True)
    log_file_path = log_folder_path / create_log_file_name()
    return str(log_file_path)


def get_gmt_offset_string():
    # from - https://stackoverflow.com/a/53860920/14662833
    gmt_offset_int = int(time.localtime().tm_gmtoff / 60 / 60)
    return f"{gmt_offset_int:+}"


def create_log_file_name():
    return "log_" + get_iso6201_time_string() + ".log"


def get_iso6201_time_string(timespec: str = "milliseconds", make_filename_friendly: bool = True):
    iso6201_timestamp = datetime.now().isoformat(timespec=timespec)
    gmt_offset_string = f"_gmt{get_gmt_offset_string()}"
    iso6201_timestamp_w_gmt = iso6201_timestamp + gmt_offset_string
    if make_filename_friendly:
        iso6201_timestamp_w_gmt = iso6201_timestamp_w_gmt.replace(":", "_")
        iso6201_timestamp_w_gmt = iso6201_timestamp_w_gmt.replace(".", "ms")
    return iso6201_timestamp_w_gmt


def default_session_name(string_tag: str = None):
    if string_tag is not None:
        string_tag = f"_{string_tag}"
    else:
        string_tag = ""

    return time.strftime(get_iso6201_time_string(timespec="seconds") + string_tag)


def get_default_recording_name(string_tag: str = None):
    if string_tag is not None and not string_tag == "":
        string_tag = f"_{string_tag}"
    else:
        string_tag = ""

    full_time = get_iso6201_time_string(timespec="seconds")
    just_hours_minutes_seconds = full_time.split("T")[1]
    recording_name = just_hours_minutes_seconds + string_tag

    logger.info(f"Generated new recording name: {recording_name}")

    return recording_name


def create_new_synchronized_videos_folder(recording_folder_path: Union[str, Path],
                                          ):
    folder_path = Path(recording_folder_path) / SYNCHRONIZED_VIDEOS_FOLDER_NAME
    folder_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Creating new recording video folder: {folder_path}")
    return str(folder_path)

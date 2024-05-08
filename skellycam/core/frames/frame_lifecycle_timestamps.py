import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass  # dataclass not Pydantic model bc its marginally faster
class FrameLifeCycleTimestamps:
    pre_grab_call: Optional[int] = None
    post_grab_return: Optional[int] = None
    start_wait_for_retrieve_trigger: Optional[int] = None
    pre_retrieve_call: Optional[int] = None
    post_retrieve_return: Optional[int] = None
    pre_calc_checksum: Optional[int] = None
    post_calc_checksum: Optional[int] = None
    pre_pickle: Optional[int] = None
    post_pickle: Optional[int] = None
    post_create_frame_from_buffer: Optional[int] = None
    post_copy_image_from_buffer: Optional[int] = None
    pre_set_image_in_frame: Optional[int] = None
    post_set_image_in_frame: Optional[int] = None
    done_create_from_buffer: Optional[int] = None

    creation: Dict[str, int] = field(
        default_factory=lambda: {"time.time_ns()": time.time_ns(),
                                 "time.perf_counter_ns()": time.perf_counter_ns()})

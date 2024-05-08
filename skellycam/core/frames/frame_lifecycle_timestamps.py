import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

perf_counter_ns_size = sys.getsizeof(time.perf_counter_ns())
placeholder = bytearray(perf_counter_ns_size)
placeholder_size = sys.getsizeof(placeholder)
if placeholder_size != perf_counter_ns_size:
    raise ValueError(f"The size of the placeholder bytearray ({placeholder_size})"
                     f" must be the same as the size of a perf_counter_ns ({perf_counter_ns_size})")

@dataclass  # dataclass not Pydantic model bc its marginally faster
class FrameLifeCycleTimestamps:
    pre_grab_call: Optional[int] = placeholder
    post_grab_return: Optional[int] = placeholder
    start_wait_for_retrieve_trigger: Optional[int] = placeholder
    pre_retrieve_call: Optional[int] = placeholder
    post_retrieve_return: Optional[int] = placeholder
    pre_calc_checksum: Optional[int] = placeholder
    post_calc_checksum: Optional[int] = placeholder
    pre_pickle: Optional[int] = placeholder
    post_pickle: Optional[int] = placeholder
    post_create_frame_from_buffer: Optional[int] = placeholder
    post_copy_image_from_buffer: Optional[int] = placeholder
    pre_set_image_in_frame: Optional[int] = placeholder
    post_set_image_in_frame: Optional[int] = placeholder
    done_create_from_buffer: Optional[int] = placeholder

    creation: Dict[str, int] = field(
        default_factory=lambda: {"time.time_ns()": time.time_ns(),
                                 "time.perf_counter_ns()": time.perf_counter_ns()})

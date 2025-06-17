import time

import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class FrameLifespanTimestamps(BaseModel):
    frame_initialized_ns: int = Field(default_factory=time.perf_counter_ns,
                                      description="Timestamp when the frame was initialized")
    pre_grab_ns: int = Field(default=0, description="Timestamp before grabbing the frame with cv2.grab()")
    post_grab_ns: int = Field(default=0, description="Timestamp after grabbing the frame with cv2.grab()")
    pre_retrieve_ns: int = Field(default=0, description="Timestamp before retrieving the frame with cv2.retrieve()")
    post_retrieve_ns: int = Field(default=0, description="Timestamp after retrieving the frame with cv2.retrieve()")
    copy_to_camera_shm_ns: int = Field(default=0, description="Copied to the per-camera shared memory buffer")
    retrieve_from_camera_shm_ns: int = Field(default=0,
                                             description="Retrieved from the per-camera shared memory buffer")
    copy_to_multiframe_shm_ns: int = Field(default=0,
                                           description="Copied to the multi-frame escape shared memory buffer")
    retrieve_from_multiframe_shm_ns: int = Field(default=0,
                                                 description="Retreived from the multi-frame escape shared memory buffer")

    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            frame_initialized_ns=array.frame_metadata_initialized,
            pre_grab_ns=array.pre_grab_ns,
            post_grab_ns=array.post_grab_ns,
            pre_retrieve_ns=array.pre_retrieve_ns,
            post_retrieve_ns=array.post_retrieve_ns,
            copy_to_camera_shm_ns=array.copy_to_camera_shm_ns,
            retrieve_from_camera_shm_ns=array.retrieve_from_camera_shm_ns,
            copy_to_multiframe_shm_ns=array.copy_to_multiframe_shm_ns,
            retrieve_from_multiframe_shm_ns=array.retrieve_from_multiframe_shm_ns,
        )

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FrameLifespanTimestamps to a numpy record array.
        """
        # Create a record array with the correct shape (1,)
        result = np.recarray(1, dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

        # Assign values to the record array
        result.frame_metadata_initialized[0] = self.frame_initialized_ns
        result.pre_grab_ns[0] = self.pre_grab_ns
        result.post_grab_ns[0] = self.post_grab_ns
        result.pre_retrieve_ns[0] = self.pre_retrieve_ns
        result.post_retrieve_ns[0] = self.post_retrieve_ns
        result.copy_to_camera_shm_ns[0] = self.copy_to_camera_shm_ns
        result.retrieve_from_camera_shm_ns[0] = self.retrieve_from_camera_shm_ns
        result.copy_to_multiframe_shm_ns[0] = self.copy_to_multiframe_shm_ns
        result.retrieve_from_multiframe_shm_ns[0] = self.retrieve_from_multiframe_shm_ns

        return result

    @property
    @computed_field
    def timestamp_ns(self) -> int:
        """
        Using the midpoint between pre and post grab timestamps to represent the frame's timestamp.
        """
        if self.pre_grab_ns is None or self.post_grab_ns is None:
            raise ValueError("pre_retrieve_ns and post_grab_ns cannot be None")
        return (self.post_grab_ns - self.pre_grab_ns) // 2

    # Individual timing metrics - Frame Acquisition
    @property
    @computed_field
    def idle_before_grab_ns(self) -> int:
        if self.frame_initialized_ns and self.pre_grab_ns:
            return self.pre_grab_ns - self.frame_initialized_ns
        return -1

    @property
    @computed_field
    def frame_grab_duration_ns(self) -> int:
        if self.post_grab_ns and self.pre_grab_ns:
            return self.post_grab_ns - self.pre_grab_ns
        return -1

    @property
    @computed_field
    def idle_before_retrieve_ns(self) -> int:
        if self.pre_retrieve_ns and self.post_grab_ns:
            return self.pre_retrieve_ns - self.post_grab_ns
        return -1

    @property
    @computed_field
    def frame_retrieve_duration_ns(self) -> int:
        if self.post_retrieve_ns and self.pre_retrieve_ns:
            return self.post_retrieve_ns - self.pre_retrieve_ns
        return -1

    # Individual timing metrics - Camera Buffer Operations
    @property
    @computed_field
    def idle_before_copy_to_camera_shm_ns(self) -> int:
        if self.copy_to_camera_shm_ns and self.post_retrieve_ns:
            return self.copy_to_camera_shm_ns - self.post_retrieve_ns
        return -1

    @property
    @computed_field
    def time_in_camera_shm_ns(self) -> int:
        if self.retrieve_from_camera_shm_ns and self.copy_to_camera_shm_ns:
            return self.retrieve_from_camera_shm_ns - self.copy_to_camera_shm_ns
        return -1

    # Individual timing metrics - Multi-Frame Operations
    @property
    @computed_field
    def idle_before_copy_to_multiframe_shm_ns(self) -> int:
        if self.copy_to_multiframe_shm_ns and self.retrieve_from_camera_shm_ns:
            return self.copy_to_multiframe_shm_ns - self.retrieve_from_camera_shm_ns
        return -1

    @property
    @computed_field
    def time_in_multiframe_shm(self) -> int:
        if self.retrieve_from_multiframe_shm_ns and self.copy_to_multiframe_shm_ns:
            return self.retrieve_from_multiframe_shm_ns - self.copy_to_multiframe_shm_ns
        return -1

    # Higher-level category timing metrics
    @property
    @computed_field
    def total_frame_acquisition_time_ns(self) -> int:
        """Total time spent in frame acquisition (grab + retrieve)"""
        if self.post_retrieve_ns and self.pre_grab_ns:
            return self.post_retrieve_ns - self.pre_grab_ns
        return -1

    @property
    @computed_field
    def total_ipc_travel_time(self) -> int:
        """Total time spent in IPC operations (after frame grab/retrieve, before exiting mf shm"""
        if self.retrieve_from_multiframe_shm_ns and self.post_retrieve_ns:
            return self.retrieve_from_multiframe_shm_ns - self.post_retrieve_ns
        return -1











    #
# def ns_to_ms(ns: int) -> float:
#     """Convert nanoseconds to milliseconds"""
#     return ns / 1_000_000
#
#
# def print_timing_report(timestamps: FrameLifespanTimestamps) -> None:
#     """Print a detailed timing report for a frame's lifecycle"""
#     print("\n=== Frame Lifecycle Timing Report ===")
#
#     # Individual timing metrics
#     print("\n--- Individual Timing Metrics (ms) ---")
#     print(f"Time before grab signal: {ns_to_ms(timestamps.idle_before_grab):.3f} ms")
#     print(f"Time spent grabbing frame: {ns_to_ms(timestamps.time_spent_grabbing_frame_ns):.3f} ms")
#     print(f"Time waiting to retrieve: {ns_to_ms(timestamps.time_waiting_to_retrieve_ns):.3f} ms")
#     print(f"Time spent retrieving: {ns_to_ms(timestamps.time_spent_retrieving_ns):.3f} ms")
#     print(f"Time waiting to be put into camera SHM buffer: {ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_camera_shm_ns):.3f} ms")
#     print(f"Time spent in camera SHM buffer: {ns_to_ms(timestamps.time_spent_in_camera_shm_ns):.3f} ms")
#     print(f"Time waiting to be put into multi-frame payload: {ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_payload_ns):.3f} ms")
#     print(f"Time waiting to be put into multi-frame escape SHM buffer: {ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns):.3f} ms")
#     print(f"Time spent in multi-frame escape SHM buffer: {ns_to_ms(timestamps.time_spent_in_multi_frame_escape_shm_buffer_ns):.3f} ms")
#     print(f"Time waiting to start resize: {ns_to_ms(timestamps.time_spent_waiting_to_start_resize_image_ns):.3f} ms")
#     print(f"Time spent in resize: {ns_to_ms(timestamps.time_spent_in_resize_image_ns):.3f} ms")
#     print(f"Time waiting to start annotation: {ns_to_ms(timestamps.time_spent_waiting_to_start_annotation_ns):.3f} ms")
#     print(f"Time spent in annotation: {ns_to_ms(timestamps.time_spent_in_annotation_ns):.3f} ms")
#     print(f"Time waiting to start JPEG compression: {ns_to_ms(timestamps.time_spent_waiting_to_start_compress_to_jpeg_ns):.3f} ms")
#     print(f"Time spent in JPEG compression: {ns_to_ms(timestamps.time_spent_in_compress_to_jpeg_ns):.3f} ms")
#
#     # Higher-level category timing metrics
#     print("\n--- Higher-Level Category Timing Metrics (ms) ---")
#     print(f"Total frame acquisition time: {ns_to_ms(timestamps.total_frame_acquisition_time_ns):.3f} ms")
#     print(f"Total camera buffer operations time: {ns_to_ms(timestamps.total_camera_buffer_operations_time_ns):.3f} ms")
#     print(f"Total multi-frame operations time: {ns_to_ms(timestamps.total_multi_frame_operations_time_ns):.3f} ms")
#     print(f"Total resize operations time: {ns_to_ms(timestamps.total_resize_operations_time_ns):.3f} ms")
#     print(f"Total annotation operations time: {ns_to_ms(timestamps.total_annotation_operations_time_ns):.3f} ms")
#     print(f"Total compression operations time: {ns_to_ms(timestamps.total_compression_operations_time_ns):.3f} ms")
#     print(f"Total image processing time: {ns_to_ms(timestamps.total_image_processing_time_ns):.3f} ms")
#     print(f"Total waiting time: {ns_to_ms(timestamps.total_waiting_time_ns):.3f} ms")
#     print(f"Total buffer time: {ns_to_ms(timestamps.total_buffer_time_ns):.3f} ms")
#
#     # Overall metrics
#     print("\n--- Overall Metrics ---")
#     print(f"Total frame processing time: {ns_to_ms(timestamps.total_frame_processing_time_ns):.3f} ms")
#
#
# def create_simulated_frame_lifecycle():
#     # Create a simulated frame lifecycle with realistic timing
#     current_time_ns = time.time_ns()
#
#     # Simulate a frame lifecycle with realistic timing
#     return FrameLifespanTimestamps(
#         frame_initialized_ns=current_time_ns,
#         pre_grab_ns=current_time_ns + 500_000,  # 0.5ms after initialization
#         post_grab_ns=current_time_ns + 3_500_000,  # 3ms for grab
#         pre_retrieve_ns=current_time_ns + 4_000_000,  # 0.5ms waiting
#         post_retrieve_ns=current_time_ns + 6_000_000,  # 2ms for retrieve
#         copy_to_camera_shm_ns=current_time_ns + 6_500_000,  # 0.5ms waiting
#         retrieve_from_camera_shm_ns=current_time_ns + 8_500_000,  # 2ms in buffer
#         copy_to_multiframe_shm_ns=current_time_ns + 10_000_000,  # 1ms waiting
#         retrieve_from_multiframe_shm_ns=current_time_ns + 12_000_000,  # 2ms in buffer
#     )
# def calculate_and_print_timing_report(timestamps:FrameLifespanTimestamps|None=None):
#     from tabulate import tabulate
#
#     if timestamps is None:
#         timestamps = create_simulated_frame_lifecycle()
#
#
#     # Create tables for the timing report
#     print("\n=== Frame Lifecycle Timing Report ===")
#
#     # Individual timing metrics table
#     individual_metrics = [
#         ["Frame Acquisition", "Time before grab signal", f"{ns_to_ms(timestamps.idle_before_grab):.3f}"],
#         ["", "Time spent grabbing frame", f"{ns_to_ms(timestamps.time_spent_grabbing_frame_ns):.3f}"],
#         ["", "Time waiting to retrieve", f"{ns_to_ms(timestamps.time_waiting_to_retrieve_ns):.3f}"],
#         ["", "Time spent retrieving", f"{ns_to_ms(timestamps.time_spent_retrieving_ns):.3f}"],
#         ["Camera Buffer", "Time waiting for camera SHM buffer", f"{ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_camera_shm_ns):.3f}"],
#         ["", "Time in camera SHM buffer", f"{ns_to_ms(timestamps.time_spent_in_camera_shm_ns):.3f}"],
#         ["Multi-Frame", "Time waiting for multi-frame payload", f"{ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_payload_ns):.3f}"],
#         ["", "Time waiting for multi-frame escape buffer", f"{ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns):.3f}"],
#         ["", "Time in multi-frame escape buffer", f"{ns_to_ms(timestamps.time_spent_in_multi_frame_escape_shm_buffer_ns):.3f}"],
#         ["Image Processing", "Time waiting to start resize", f"{ns_to_ms(timestamps.time_spent_waiting_to_start_resize_image_ns):.3f}"],
#         ["", "Time spent in resize", f"{ns_to_ms(timestamps.time_spent_in_resize_image_ns):.3f}"],
#         ["", "Time waiting to start annotation", f"{ns_to_ms(timestamps.time_spent_waiting_to_start_annotation_ns):.3f}"],
#         ["", "Time spent in annotation", f"{ns_to_ms(timestamps.time_spent_in_annotation_ns):.3f}"],
#         ["", "Time waiting to start JPEG compression", f"{ns_to_ms(timestamps.time_spent_waiting_to_start_compress_to_jpeg_ns):.3f}"],
#         ["", "Time spent in JPEG compression", f"{ns_to_ms(timestamps.time_spent_in_compress_to_jpeg_ns):.3f}"],
#     ]
#
#     print("\n--- Individual Timing Metrics (ms) ---")
#     print(tabulate(individual_metrics, headers=["Category", "Operation", "Time (ms)"], tablefmt="fancy_grid"))
#
#     # Higher-level category timing metrics table
#     category_metrics = [
#         ["Frame Acquisition", f"{ns_to_ms(timestamps.total_frame_acquisition_time_ns):.3f}"],
#         ["Camera Buffer Operations", f"{ns_to_ms(timestamps.total_camera_buffer_operations_time_ns):.3f}"],
#         ["Multi-Frame Operations", f"{ns_to_ms(timestamps.total_multi_frame_operations_time_ns):.3f}"],
#         ["Resize Operations", f"{ns_to_ms(timestamps.total_resize_operations_time_ns):.3f}"],
#         ["Annotation Operations", f"{ns_to_ms(timestamps.total_annotation_operations_time_ns):.3f}"],
#         ["Compression Operations", f"{ns_to_ms(timestamps.total_compression_operations_time_ns):.3f}"],
#         ["Total Image Processing", f"{ns_to_ms(timestamps.total_image_processing_time_ns):.3f}"],
#         ["Total Waiting Time", f"{ns_to_ms(timestamps.total_waiting_time_ns):.3f}"],
#         ["Total Buffer Time", f"{ns_to_ms(timestamps.total_buffer_time_ns):.3f}"],
#         ["Total Frame Processing", f"{ns_to_ms(timestamps.total_frame_processing_time_ns):.3f}"],
#     ]
#
#     print("\n--- Higher-Level Category Timing Metrics (ms) ---")
#     print(tabulate(category_metrics, headers=["Category", "Time (ms)"], tablefmt="fancy_grid"))
#
#     # Create a visual representation of the frame lifecycle timeline
#     timeline_data = []
#     start_time = timestamps.frame_initialized_ns
#     end_time = max(
#         timestamps.end_annotation_ns or 0,
#         timestamps.end_compress_to_jpeg_ns or 0,
#         timestamps.retrieve_from_multiframe_shm_ns or 0
#     )
#     total_time_ms = (end_time - start_time) / 1_000_000
#
#     # Calculate percentage of total time for each operation
#     timeline_data = [
#         ["Initialization to Grab", 0, ns_to_ms(timestamps.pre_grab_ns - timestamps.frame_initialized_ns)],
#         ["Frame Grab", ns_to_ms(timestamps.pre_grab_ns - timestamps.frame_initialized_ns),
#                       ns_to_ms(timestamps.post_grab_ns - timestamps.frame_initialized_ns)],
#         ["Wait for Retrieve", ns_to_ms(timestamps.post_grab_ns - timestamps.frame_initialized_ns),
#                             ns_to_ms(timestamps.pre_retrieve_ns - timestamps.frame_initialized_ns)],
#         ["Frame Retrieve", ns_to_ms(timestamps.pre_retrieve_ns - timestamps.frame_initialized_ns),
#                          ns_to_ms(timestamps.post_retrieve_ns - timestamps.frame_initialized_ns)],
#         ["Camera SHM Buffer", ns_to_ms(timestamps.copy_to_camera_shm_ns - timestamps.frame_initialized_ns),
#                             ns_to_ms(timestamps.retrieve_from_camera_shm_ns - timestamps.frame_initialized_ns)],
#         ["Multi-Frame Operations", ns_to_ms(timestamps.retrieve_from_camera_shm_ns - timestamps.frame_initialized_ns),
#                                  ns_to_ms(timestamps.retrieve_from_multiframe_shm_ns - timestamps.frame_initialized_ns)],
#         ["Resize Image", ns_to_ms(timestamps.start_resize_image_ns - timestamps.frame_initialized_ns),
#                        ns_to_ms(timestamps.end_resize_image_ns - timestamps.frame_initialized_ns)],
#         ["Annotation", ns_to_ms(timestamps.start_annotation_ns - timestamps.frame_initialized_ns),
#                      ns_to_ms(timestamps.end_annotation_ns - timestamps.frame_initialized_ns)],
#         ["JPEG Compression", ns_to_ms(timestamps.start_compress_to_jpeg_ns - timestamps.frame_initialized_ns),
#                            ns_to_ms(timestamps.end_compress_to_jpeg_ns - timestamps.frame_initialized_ns)],
#     ]
#
#     # Create a visual timeline
#     print("\n--- Frame Lifecycle Timeline ---")
#     print(f"Total processing time: {total_time_ms:.3f} ms")
#
#     # Create a visual bar chart
#     bar_width = 50  # Width of the timeline in characters
#     timeline_bars = []
#
#     for operation, start_ms, end_ms in timeline_data:
#         start_pos = int((start_ms / total_time_ms) * bar_width)
#         end_pos = int((end_ms / total_time_ms) * bar_width)
#         width = max(1, end_pos - start_pos)
#
#         bar = " " * start_pos + "█" * width + " " * (bar_width - end_pos)
#         timeline_bars.append([operation, f"{start_ms:.1f}", f"{end_ms:.1f}", bar])
#
#     print(tabulate(timeline_bars, headers=["Operation", "Start (ms)", "End (ms)", "Timeline"], tablefmt="simple"))
#
#     # Test conversion to numpy record array and back
#     record_array = timestamps.to_numpy_record_array()
#     print("\n=== Testing Conversion to NumPy Record Array ===")
#     print(f"Record array shape: {record_array.shape}")
#     print(f"Record array dtype: {record_array.dtype}")
# #
# #     # Convert back to FrameLifespanTimestamps
# #     timestamps_from_array = FrameLifespanTimestamps.from_numpy_record_array(record_array)
# #     print("\n=== Testing Conversion from NumPy Record Array ===")
# #     print(f"Timestamps match: {timestamps.model_dump() == timestamps_from_array.model_dump()}")
# #
#
# if __name__ == "__main__":
#
#     calculate_and_print_timing_report()

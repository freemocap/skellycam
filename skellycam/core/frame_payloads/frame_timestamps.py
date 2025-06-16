import time
import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class FrameLifespanTimestamps(BaseModel):
    initialized_timestamp_ns: int = Field(default_factory=time.perf_counter_ns,description="Timestamp when the frame was initialized")
    pre_grab_timestamp_ns: int = Field(default=0,description="Timestamp before grabbing the frame with cv2.grab()")
    post_grab_timestamp_ns: int = Field(default=0,description="Timestamp after grabbing the frame with cv2.grab()")
    pre_retrieve_timestamp_ns: int = Field(default=0,description="Timestamp before retrieving the frame with cv2.retrieve()")
    post_retrieve_timestamp_ns: int = Field(default=0,description="Timestamp after retrieving the frame with cv2.retrieve()")
    copy_to_camera_shm_buffer_timestamp_ns: int = Field(default=0,description="Copied to the per-camera shared memory buffer")
    copy_from_camera_shm_buffer_timestamp_ns: int = Field(default=0,description="Copied from the per-camera shared memory buffer")
    put_into_multi_frame_payload: int = Field(default=0,description="Put into the multi-frame payload")
    copy_to_multi_frame_escape_shm_buffer_timestamp_ns: int = Field(default=0,description="Copied to the multi-frame escape shared memory buffer")
    copy_from_multi_frame_escape_shm_buffer_timestamp_ns: int = Field(default=0,description="Copied from the multi-frame escape shared memory buffer")
    start_resize_image_timestamp_ns: int = Field(default=0,description="Image resizing started")
    end_resize_image_timestamp_ns: int = Field(default=0,description="Image resizing ended")
    start_compress_to_jpeg_timestamp_ns: int = Field(default=0,description="JPEG compression started")
    end_compress_to_jpeg_timestamp_ns: int = Field(default=0,description="JPEG compression ended")
    start_annotation_timestamp_ns: int = Field(default=0,description="Image annotation started")
    end_annotation_timestamp_ns: int = Field(default=0,description="Image annotation ended")

    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            initialized_timestamp_ns=array.frame_metadata_initialized,
            pre_grab_timestamp_ns=array.pre_grab_timestamp_ns,
            post_grab_timestamp_ns=array.post_grab_timestamp_ns,
            pre_retrieve_timestamp_ns=array.pre_retrieve_timestamp_ns,
            post_retrieve_timestamp_ns=array.post_retrieve_timestamp_ns,
            copy_to_camera_shm_buffer_timestamp_ns=array.copy_to_camera_shm_buffer_timestamp_ns,
            copy_from_camera_shm_buffer_timestamp_ns=array.copy_from_camera_shm_buffer_timestamp_ns,
            put_into_multi_frame_payload=array.put_into_multi_frame_payload,
            copy_to_multi_frame_escape_shm_buffer_timestamp_ns=array.copy_to_multi_frame_escape_shm_buffer_timestamp_ns,
            copy_from_multi_frame_escape_shm_buffer_timestamp_ns=array.copy_from_multi_frame_escape_shm_buffer_timestamp_ns,
            start_resize_image_timestamp_ns=array.start_resize_image_timestamp_ns,
            end_resize_image_timestamp_ns=array.end_resize_image_timestamp_ns,
            start_compress_to_jpeg_timestamp_ns=array.start_compress_to_jpeg_timestamp_ns,
            end_compress_to_jpeg_timestamp_ns=array.end_compress_to_jpeg_timestamp_ns,
            start_annotation_timestamp_ns=array.start_image_annotation_timestamp_ns,
            end_annotation_timestamp_ns=array.end_image_annotation_timestamp_ns,
        )

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FrameLifespanTimestamps to a numpy record array.
        """
        # Create a record array with the correct shape (1,)
        result = np.recarray(1, dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

        # Assign values to the record array
        result.frame_metadata_initialized[0] = self.initialized_timestamp_ns
        result.pre_grab_timestamp_ns[0] = self.pre_grab_timestamp_ns
        result.post_grab_timestamp_ns[0] = self.post_grab_timestamp_ns
        result.pre_retrieve_timestamp_ns[0] = self.pre_retrieve_timestamp_ns
        result.post_retrieve_timestamp_ns[0] = self.post_retrieve_timestamp_ns
        result.copy_to_camera_shm_buffer_timestamp_ns[0] = self.copy_to_camera_shm_buffer_timestamp_ns
        result.copy_from_camera_shm_buffer_timestamp_ns[0] = self.copy_from_camera_shm_buffer_timestamp_ns
        result.put_into_multi_frame_payload[0] = self.put_into_multi_frame_payload
        result.copy_to_multi_frame_escape_shm_buffer_timestamp_ns[
            0] = self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns
        result.copy_from_multi_frame_escape_shm_buffer_timestamp_ns[
            0] = self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns
        result.start_resize_image_timestamp_ns[0] = self.start_resize_image_timestamp_ns
        result.end_resize_image_timestamp_ns[0] = self.end_resize_image_timestamp_ns
        result.start_image_annotation_timestamp_ns[0] = self.start_annotation_timestamp_ns
        result.end_image_annotation_timestamp_ns[0] = self.end_annotation_timestamp_ns
        result.start_compress_to_jpeg_timestamp_ns[0] = self.start_compress_to_jpeg_timestamp_ns
        result.end_compress_to_jpeg_timestamp_ns[0] = self.end_compress_to_jpeg_timestamp_ns

        return result

    # Individual timing metrics - Frame Acquisition
    @computed_field
    def time_before_grab_signal_ns(self) -> int:
        if self.initialized_timestamp_ns and self.pre_grab_timestamp_ns:
            return self.pre_grab_timestamp_ns - self.initialized_timestamp_ns
        return -1

    @computed_field
    def time_spent_grabbing_frame_ns(self) -> int:
        if self.post_grab_timestamp_ns and self.pre_grab_timestamp_ns:
            return self.post_grab_timestamp_ns - self.pre_grab_timestamp_ns
        return -1

    @computed_field
    def time_waiting_to_retrieve_ns(self) -> int:
        if self.pre_retrieve_timestamp_ns and self.post_grab_timestamp_ns:
            return self.pre_retrieve_timestamp_ns - self.post_grab_timestamp_ns
        return -1

    @computed_field
    def time_spent_retrieving_ns(self) -> int:
        if self.post_retrieve_timestamp_ns and self.pre_retrieve_timestamp_ns:
            return self.post_retrieve_timestamp_ns - self.pre_retrieve_timestamp_ns
        return -1

    # Individual timing metrics - Camera Buffer Operations
    @computed_field
    def time_spent_waiting_to_be_put_into_camera_shm_buffer_ns(self) -> int:
        if self.copy_to_camera_shm_buffer_timestamp_ns and self.post_retrieve_timestamp_ns:
            return self.copy_to_camera_shm_buffer_timestamp_ns - self.post_retrieve_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_camera_shm_buffer_ns(self) -> int:
        if self.copy_from_camera_shm_buffer_timestamp_ns and self.copy_to_camera_shm_buffer_timestamp_ns:
            return self.copy_from_camera_shm_buffer_timestamp_ns - self.copy_to_camera_shm_buffer_timestamp_ns
        return -1

    # Individual timing metrics - Multi-Frame Operations
    @computed_field
    def time_spent_waiting_to_be_put_into_multi_frame_payload_ns(self) -> int:
        if self.put_into_multi_frame_payload and self.copy_from_camera_shm_buffer_timestamp_ns:
            return self.put_into_multi_frame_payload - self.copy_from_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns(self) -> int:
        if self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns and self.copy_from_camera_shm_buffer_timestamp_ns:
            return self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns - self.copy_from_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_multi_frame_escape_shm_buffer_ns(self) -> int:
        if self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns and self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns:
            return self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns - self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns
        return -1

    # Individual timing metrics - Image Processing
    @computed_field
    def time_spent_waiting_to_start_resize_image_ns(self) -> int:
        if self.start_resize_image_timestamp_ns and self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns:
            return self.start_resize_image_timestamp_ns - self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_resize_image_ns(self) -> int:
        if self.end_resize_image_timestamp_ns and self.start_resize_image_timestamp_ns:
            return self.end_resize_image_timestamp_ns - self.start_resize_image_timestamp_ns
        return -1

    @computed_field
    def time_spent_waiting_to_start_annotation_ns(self) -> int:
        if self.start_annotation_timestamp_ns and self.end_resize_image_timestamp_ns:
            return self.start_annotation_timestamp_ns - self.end_resize_image_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_annotation_ns(self) -> int:
        if self.end_annotation_timestamp_ns and self.start_annotation_timestamp_ns:
            return self.end_annotation_timestamp_ns - self.start_annotation_timestamp_ns
        return -1

    @computed_field
    def time_spent_waiting_to_start_compress_to_jpeg_ns(self) -> int:
        if self.start_compress_to_jpeg_timestamp_ns and self.copy_from_camera_shm_buffer_timestamp_ns:
            return self.start_compress_to_jpeg_timestamp_ns - self.copy_from_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_compress_to_jpeg_ns(self) -> int:
        if self.end_compress_to_jpeg_timestamp_ns and self.start_compress_to_jpeg_timestamp_ns:
            return self.end_compress_to_jpeg_timestamp_ns - self.start_compress_to_jpeg_timestamp_ns
        return -1

    # Higher-level category timing metrics
    @computed_field
    def total_frame_acquisition_time_ns(self) -> int:
        """Total time spent in frame acquisition (grab + retrieve)"""
        if self.post_retrieve_timestamp_ns and self.pre_grab_timestamp_ns:
            return self.post_retrieve_timestamp_ns - self.pre_grab_timestamp_ns
        return -1

    @computed_field
    def total_camera_buffer_operations_time_ns(self) -> int:
        """Total time from post-retrieve to being copied from camera shared memory buffer"""
        if self.copy_from_camera_shm_buffer_timestamp_ns and self.post_retrieve_timestamp_ns:
            return self.copy_from_camera_shm_buffer_timestamp_ns - self.post_retrieve_timestamp_ns
        return -1

    @computed_field
    def total_multi_frame_operations_time_ns(self) -> int:
        """Total time spent in multi-frame operations"""
        start_time = self.copy_from_camera_shm_buffer_timestamp_ns
        end_time = self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns
        
        if start_time and end_time:
            return end_time - start_time
        return -1

    @computed_field
    def total_resize_operations_time_ns(self) -> int:
        """Total time spent in resize operations including waiting"""
        if self.end_resize_image_timestamp_ns and self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns:
            return self.end_resize_image_timestamp_ns - self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def total_annotation_operations_time_ns(self) -> int:
        """Total time spent in annotation operations including waiting"""
        if self.end_annotation_timestamp_ns and self.end_resize_image_timestamp_ns:
            return self.end_annotation_timestamp_ns - self.end_resize_image_timestamp_ns
        return -1

    @computed_field
    def total_compression_operations_time_ns(self) -> int:
        """Total time spent in JPEG compression operations including waiting"""
        if self.end_compress_to_jpeg_timestamp_ns and self.copy_from_camera_shm_buffer_timestamp_ns:
            return self.end_compress_to_jpeg_timestamp_ns - self.copy_from_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def total_image_processing_time_ns(self) -> int:
        """Total time spent in image processing (resize + annotation + compression)"""
        resize_time = self.time_spent_in_resize_image_ns if self.time_spent_in_resize_image_ns > 0 else 0
        annotation_time = self.time_spent_in_annotation_ns if self.time_spent_in_annotation_ns > 0 else 0
        compression_time = self.time_spent_in_compress_to_jpeg_ns if self.time_spent_in_compress_to_jpeg_ns > 0 else 0
        
        total = resize_time + annotation_time + compression_time
        return total if total > 0 else -1

    @computed_field
    def total_waiting_time_ns(self) -> int:
        """Total time spent waiting between operations"""
        waiting_times = [
            self.time_before_grab_signal_ns if self.time_before_grab_signal_ns > 0 else 0,
            self.time_waiting_to_retrieve_ns if self.time_waiting_to_retrieve_ns > 0 else 0,
            self.time_spent_waiting_to_be_put_into_camera_shm_buffer_ns if self.time_spent_waiting_to_be_put_into_camera_shm_buffer_ns > 0 else 0,
            self.time_spent_waiting_to_be_put_into_multi_frame_payload_ns if self.time_spent_waiting_to_be_put_into_multi_frame_payload_ns > 0 else 0,
            self.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns if self.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns > 0 else 0,
            self.time_spent_waiting_to_start_resize_image_ns if self.time_spent_waiting_to_start_resize_image_ns > 0 else 0,
            self.time_spent_waiting_to_start_annotation_ns if self.time_spent_waiting_to_start_annotation_ns > 0 else 0,
            self.time_spent_waiting_to_start_compress_to_jpeg_ns if self.time_spent_waiting_to_start_compress_to_jpeg_ns > 0 else 0
        ]
        
        total = sum(waiting_times)
        return total if total > 0 else -1

    @computed_field
    def total_buffer_time_ns(self) -> int:
        """Total time spent in shared memory buffers"""
        camera_buffer_time = self.time_spent_in_camera_shm_buffer_ns if self.time_spent_in_camera_shm_buffer_ns > 0 else 0
        multi_frame_buffer_time = self.time_spent_in_multi_frame_escape_shm_buffer_ns if self.time_spent_in_multi_frame_escape_shm_buffer_ns > 0 else 0
        
        total = camera_buffer_time + multi_frame_buffer_time
        return total if total > 0 else -1

    @computed_field
    def total_frame_processing_time_ns(self) -> int:
        """Total time from initialization to the end of the last processing step"""
        last_timestamp = max(
            self.end_annotation_timestamp_ns or 0,
            self.end_compress_to_jpeg_timestamp_ns or 0,
            self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns or 0
        )
        
        if last_timestamp and self.initialized_timestamp_ns:
            return last_timestamp - self.initialized_timestamp_ns
        return -1


def ns_to_ms(ns: int) -> float:
    """Convert nanoseconds to milliseconds"""
    return ns / 1_000_000


def print_timing_report(timestamps: FrameLifespanTimestamps) -> None:
    """Print a detailed timing report for a frame's lifecycle"""
    print("\n=== Frame Lifecycle Timing Report ===")
    
    # Individual timing metrics
    print("\n--- Individual Timing Metrics (ms) ---")
    print(f"Time before grab signal: {ns_to_ms(timestamps.time_before_grab_signal_ns):.3f} ms")
    print(f"Time spent grabbing frame: {ns_to_ms(timestamps.time_spent_grabbing_frame_ns):.3f} ms")
    print(f"Time waiting to retrieve: {ns_to_ms(timestamps.time_waiting_to_retrieve_ns):.3f} ms")
    print(f"Time spent retrieving: {ns_to_ms(timestamps.time_spent_retrieving_ns):.3f} ms")
    print(f"Time waiting to be put into camera SHM buffer: {ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_camera_shm_buffer_ns):.3f} ms")
    print(f"Time spent in camera SHM buffer: {ns_to_ms(timestamps.time_spent_in_camera_shm_buffer_ns):.3f} ms")
    print(f"Time waiting to be put into multi-frame payload: {ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_payload_ns):.3f} ms")
    print(f"Time waiting to be put into multi-frame escape SHM buffer: {ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns):.3f} ms")
    print(f"Time spent in multi-frame escape SHM buffer: {ns_to_ms(timestamps.time_spent_in_multi_frame_escape_shm_buffer_ns):.3f} ms")
    print(f"Time waiting to start resize: {ns_to_ms(timestamps.time_spent_waiting_to_start_resize_image_ns):.3f} ms")
    print(f"Time spent in resize: {ns_to_ms(timestamps.time_spent_in_resize_image_ns):.3f} ms")
    print(f"Time waiting to start annotation: {ns_to_ms(timestamps.time_spent_waiting_to_start_annotation_ns):.3f} ms")
    print(f"Time spent in annotation: {ns_to_ms(timestamps.time_spent_in_annotation_ns):.3f} ms")
    print(f"Time waiting to start JPEG compression: {ns_to_ms(timestamps.time_spent_waiting_to_start_compress_to_jpeg_ns):.3f} ms")
    print(f"Time spent in JPEG compression: {ns_to_ms(timestamps.time_spent_in_compress_to_jpeg_ns):.3f} ms")
    
    # Higher-level category timing metrics
    print("\n--- Higher-Level Category Timing Metrics (ms) ---")
    print(f"Total frame acquisition time: {ns_to_ms(timestamps.total_frame_acquisition_time_ns):.3f} ms")
    print(f"Total camera buffer operations time: {ns_to_ms(timestamps.total_camera_buffer_operations_time_ns):.3f} ms")
    print(f"Total multi-frame operations time: {ns_to_ms(timestamps.total_multi_frame_operations_time_ns):.3f} ms")
    print(f"Total resize operations time: {ns_to_ms(timestamps.total_resize_operations_time_ns):.3f} ms")
    print(f"Total annotation operations time: {ns_to_ms(timestamps.total_annotation_operations_time_ns):.3f} ms")
    print(f"Total compression operations time: {ns_to_ms(timestamps.total_compression_operations_time_ns):.3f} ms")
    print(f"Total image processing time: {ns_to_ms(timestamps.total_image_processing_time_ns):.3f} ms")
    print(f"Total waiting time: {ns_to_ms(timestamps.total_waiting_time_ns):.3f} ms")
    print(f"Total buffer time: {ns_to_ms(timestamps.total_buffer_time_ns):.3f} ms")
    
    # Overall metrics
    print("\n--- Overall Metrics ---")
    print(f"Total frame processing time: {ns_to_ms(timestamps.total_frame_processing_time_ns):.3f} ms")


def create_simulated_frame_lifecycle():
    # Create a simulated frame lifecycle with realistic timing
    current_time_ns = time.time_ns()

    # Simulate a frame lifecycle with realistic timing
    return FrameLifespanTimestamps(
        initialized_timestamp_ns=current_time_ns,
        pre_grab_timestamp_ns=current_time_ns + 500_000,  # 0.5ms after initialization
        post_grab_timestamp_ns=current_time_ns + 3_500_000,  # 3ms for grab
        pre_retrieve_timestamp_ns=current_time_ns + 4_000_000,  # 0.5ms waiting
        post_retrieve_timestamp_ns=current_time_ns + 6_000_000,  # 2ms for retrieve
        copy_to_camera_shm_buffer_timestamp_ns=current_time_ns + 6_500_000,  # 0.5ms waiting
        copy_from_camera_shm_buffer_timestamp_ns=current_time_ns + 8_500_000,  # 2ms in buffer
        put_into_multi_frame_payload=current_time_ns + 9_000_000,  # 0.5ms waiting
        copy_to_multi_frame_escape_shm_buffer_timestamp_ns=current_time_ns + 10_000_000,  # 1ms waiting
        copy_from_multi_frame_escape_shm_buffer_timestamp_ns=current_time_ns + 12_000_000,  # 2ms in buffer
        start_resize_image_timestamp_ns=current_time_ns + 12_500_000,  # 0.5ms waiting
        end_resize_image_timestamp_ns=current_time_ns + 14_500_000,  # 2ms for resize
        start_annotation_timestamp_ns=current_time_ns + 15_000_000,  # 0.5ms waiting
        end_annotation_timestamp_ns=current_time_ns + 16_000_000,  # 1ms for annotation
        start_compress_to_jpeg_timestamp_ns=current_time_ns + 9_000_000,  # Parallel to multi-frame operations
        end_compress_to_jpeg_timestamp_ns=current_time_ns + 13_000_000,  # 4ms for compression
    )
def calculate_and_print_timing_report(timestamps:FrameLifespanTimestamps|None=None):
    from tabulate import tabulate

    if timestamps is None:
        timestamps = create_simulated_frame_lifecycle()


    # Create tables for the timing report
    print("\n=== Frame Lifecycle Timing Report ===")
    
    # Individual timing metrics table
    individual_metrics = [
        ["Frame Acquisition", "Time before grab signal", f"{ns_to_ms(timestamps.time_before_grab_signal_ns):.3f}"],
        ["", "Time spent grabbing frame", f"{ns_to_ms(timestamps.time_spent_grabbing_frame_ns):.3f}"],
        ["", "Time waiting to retrieve", f"{ns_to_ms(timestamps.time_waiting_to_retrieve_ns):.3f}"],
        ["", "Time spent retrieving", f"{ns_to_ms(timestamps.time_spent_retrieving_ns):.3f}"],
        ["Camera Buffer", "Time waiting for camera SHM buffer", f"{ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_camera_shm_buffer_ns):.3f}"],
        ["", "Time in camera SHM buffer", f"{ns_to_ms(timestamps.time_spent_in_camera_shm_buffer_ns):.3f}"],
        ["Multi-Frame", "Time waiting for multi-frame payload", f"{ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_payload_ns):.3f}"],
        ["", "Time waiting for multi-frame escape buffer", f"{ns_to_ms(timestamps.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns):.3f}"],
        ["", "Time in multi-frame escape buffer", f"{ns_to_ms(timestamps.time_spent_in_multi_frame_escape_shm_buffer_ns):.3f}"],
        ["Image Processing", "Time waiting to start resize", f"{ns_to_ms(timestamps.time_spent_waiting_to_start_resize_image_ns):.3f}"],
        ["", "Time spent in resize", f"{ns_to_ms(timestamps.time_spent_in_resize_image_ns):.3f}"],
        ["", "Time waiting to start annotation", f"{ns_to_ms(timestamps.time_spent_waiting_to_start_annotation_ns):.3f}"],
        ["", "Time spent in annotation", f"{ns_to_ms(timestamps.time_spent_in_annotation_ns):.3f}"],
        ["", "Time waiting to start JPEG compression", f"{ns_to_ms(timestamps.time_spent_waiting_to_start_compress_to_jpeg_ns):.3f}"],
        ["", "Time spent in JPEG compression", f"{ns_to_ms(timestamps.time_spent_in_compress_to_jpeg_ns):.3f}"],
    ]
    
    print("\n--- Individual Timing Metrics (ms) ---")
    print(tabulate(individual_metrics, headers=["Category", "Operation", "Time (ms)"], tablefmt="fancy_grid"))
    
    # Higher-level category timing metrics table
    category_metrics = [
        ["Frame Acquisition", f"{ns_to_ms(timestamps.total_frame_acquisition_time_ns):.3f}"],
        ["Camera Buffer Operations", f"{ns_to_ms(timestamps.total_camera_buffer_operations_time_ns):.3f}"],
        ["Multi-Frame Operations", f"{ns_to_ms(timestamps.total_multi_frame_operations_time_ns):.3f}"],
        ["Resize Operations", f"{ns_to_ms(timestamps.total_resize_operations_time_ns):.3f}"],
        ["Annotation Operations", f"{ns_to_ms(timestamps.total_annotation_operations_time_ns):.3f}"],
        ["Compression Operations", f"{ns_to_ms(timestamps.total_compression_operations_time_ns):.3f}"],
        ["Total Image Processing", f"{ns_to_ms(timestamps.total_image_processing_time_ns):.3f}"],
        ["Total Waiting Time", f"{ns_to_ms(timestamps.total_waiting_time_ns):.3f}"],
        ["Total Buffer Time", f"{ns_to_ms(timestamps.total_buffer_time_ns):.3f}"],
        ["Total Frame Processing", f"{ns_to_ms(timestamps.total_frame_processing_time_ns):.3f}"],
    ]
    
    print("\n--- Higher-Level Category Timing Metrics (ms) ---")
    print(tabulate(category_metrics, headers=["Category", "Time (ms)"], tablefmt="fancy_grid"))
    
    # Create a visual representation of the frame lifecycle timeline
    timeline_data = []
    start_time = timestamps.initialized_timestamp_ns
    end_time = max(
        timestamps.end_annotation_timestamp_ns or 0,
        timestamps.end_compress_to_jpeg_timestamp_ns or 0,
        timestamps.copy_from_multi_frame_escape_shm_buffer_timestamp_ns or 0
    )
    total_time_ms = (end_time - start_time) / 1_000_000
    
    # Calculate percentage of total time for each operation
    timeline_data = [
        ["Initialization to Grab", 0, ns_to_ms(timestamps.pre_grab_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Frame Grab", ns_to_ms(timestamps.pre_grab_timestamp_ns - timestamps.initialized_timestamp_ns), 
                      ns_to_ms(timestamps.post_grab_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Wait for Retrieve", ns_to_ms(timestamps.post_grab_timestamp_ns - timestamps.initialized_timestamp_ns),
                            ns_to_ms(timestamps.pre_retrieve_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Frame Retrieve", ns_to_ms(timestamps.pre_retrieve_timestamp_ns - timestamps.initialized_timestamp_ns),
                         ns_to_ms(timestamps.post_retrieve_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Camera SHM Buffer", ns_to_ms(timestamps.copy_to_camera_shm_buffer_timestamp_ns - timestamps.initialized_timestamp_ns),
                            ns_to_ms(timestamps.copy_from_camera_shm_buffer_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Multi-Frame Operations", ns_to_ms(timestamps.copy_from_camera_shm_buffer_timestamp_ns - timestamps.initialized_timestamp_ns),
                                 ns_to_ms(timestamps.copy_from_multi_frame_escape_shm_buffer_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Resize Image", ns_to_ms(timestamps.start_resize_image_timestamp_ns - timestamps.initialized_timestamp_ns),
                       ns_to_ms(timestamps.end_resize_image_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["Annotation", ns_to_ms(timestamps.start_annotation_timestamp_ns - timestamps.initialized_timestamp_ns),
                     ns_to_ms(timestamps.end_annotation_timestamp_ns - timestamps.initialized_timestamp_ns)],
        ["JPEG Compression", ns_to_ms(timestamps.start_compress_to_jpeg_timestamp_ns - timestamps.initialized_timestamp_ns),
                           ns_to_ms(timestamps.end_compress_to_jpeg_timestamp_ns - timestamps.initialized_timestamp_ns)],
    ]
    
    # Create a visual timeline
    print("\n--- Frame Lifecycle Timeline ---")
    print(f"Total processing time: {total_time_ms:.3f} ms")
    
    # Create a visual bar chart
    bar_width = 50  # Width of the timeline in characters
    timeline_bars = []
    
    for operation, start_ms, end_ms in timeline_data:
        start_pos = int((start_ms / total_time_ms) * bar_width)
        end_pos = int((end_ms / total_time_ms) * bar_width)
        width = max(1, end_pos - start_pos)
        
        bar = " " * start_pos + "█" * width + " " * (bar_width - end_pos)
        timeline_bars.append([operation, f"{start_ms:.1f}", f"{end_ms:.1f}", bar])
    
    print(tabulate(timeline_bars, headers=["Operation", "Start (ms)", "End (ms)", "Timeline"], tablefmt="simple"))
    
    # Test conversion to numpy record array and back
    record_array = timestamps.to_numpy_record_array()
    print("\n=== Testing Conversion to NumPy Record Array ===")
    print(f"Record array shape: {record_array.shape}")
    print(f"Record array dtype: {record_array.dtype}")
    
    # Convert back to FrameLifespanTimestamps
    timestamps_from_array = FrameLifespanTimestamps.from_numpy_record_array(record_array)
    print("\n=== Testing Conversion from NumPy Record Array ===")
    print(f"Timestamps match: {timestamps.model_dump() == timestamps_from_array.model_dump()}")


if __name__ == "__main__":

    calculate_and_print_timing_report()
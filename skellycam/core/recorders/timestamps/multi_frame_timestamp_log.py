from datetime import datetime

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.frame_payloads.multi_frame_payload import MultiFrameMetadata, MultiFramePayload
from skellycam.core.recorders.timestamps.camera_timestamp_log import CameraTimestampLog
from skellycam.core.types import CameraIdString


class MultiFrameTimestampLog(BaseModel):
    multi_frame_number: int = Field(
        description="The number of multi-frame payloads that have been received by the camera group, "
                    "will be the same for all cameras and corresponds to the frame number in saved videos"
    )
    timestamp_from_zero_s: float = Field(
        description="The mean timestamp of the individual frames in this multi-frame, in seconds since the first frame was received by this camera group"
    )
    timestamp_utc_s: float = Field(
        description="The mean timestamp of the frames in this multi-frame, in seconds since the Unix epoch"
    )
    timestamp_utc_iso8601: str = Field(
        description="The mean timestamp of the frames in this multi-frame, made by converting `mean_timestamp_utc_s` in ISO 8601 format, e.g. 2021-01-01T00:00:00.000000"
    )
    timestamp_local_iso8601: str = Field(
        description="The mean timestamp of the frames in this multi-frame, made by converting `mean_timestamp_local_s` in ISO 8601 format, e.g. 2021-01-01T00:00:00.000000"
    )
    inter_camera_timestamp_range_ns: float = Field(
        description="The range of timestamps between cameras, in milliseconds"
    )
    inter_camera_timestamp_stddev_ns: float = Field(
        description="The standard deviation of timestamps between cameras, in milliseconds"
    )


    mean_time_before_grab_signal_ns: float = Field(
        description="The mean time between frame initialzation and when the grab signal is sent to each camera, in nanoseconds"
    )
    stddev_time_before_grab_signal_ns: float = Field(
        description="The standard deviation of the time between frame initialzation and when the grab signal is sent to each camera, in nanoseconds"
    )
    mean_time_spent_grabbing_frame_ns: float = Field(
        description="The mean time spent grabbing the frame for each camera, in nanoseconds"
    )
    stddev_time_spent_grabbing_frame_ns: float = Field(
        description="The standard deviation of the time spent grabbing the frame for each camera, in nanoseconds"
    )
    mean_time_waiting_to_retrieve_ns: float = Field(
        description="The mean time spent waiting to retrieve the frame for each camera, in nanoseconds"
    )
    stddev_time_waiting_to_retrieve_ns: float = Field(
        description="The standard deviation of the time spent waiting to retrieve the frame for each camera, in nanoseconds"
    )
    mean_time_spent_retrieving_ns: float = Field(
        description="The mean time spent retrieving the frame for each camera, in nanoseconds"
    )
    stddev_time_spent_retrieving_ns: float = Field(
        description="The standard deviation of the time spent retrieving the frame for each camera, in nanoseconds"
    )
    mean_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns: float = Field(
        description="The mean time spent waiting to be put into the camera shared memory buffer for each camera, in nanoseconds"
    )
    stddev_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns: float = Field(
        description="The standard deviation of the time spent waiting to be put into the camera shared memory buffer for each camera, in nanoseconds"
    )
    mean_time_spent_in_camera_shm_buffer_ns: float = Field(
        description="The mean time spent in the camera shared memory buffer for each camera, in nanoseconds"
    )
    stddev_time_spent_in_camera_shm_buffer_ns: float = Field(
        description="The standard deviation of the time spent in the camera shared memory buffer for each camera, in nanoseconds"
    )
    mean_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns: float = Field(
        description="The mean time spent waiting to be put into the multi-frame escape shared memory buffer for each camera, in nanoseconds"
    )
    stddev_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns: float = Field(
        description="The standard deviation of the time spent waiting to be put into the multi-frame escape shared memory buffer for each camera, in nanoseconds"
    )
    mean_time_spent_in_multi_frame_escape_shm_buffer_ns: float = Field(
        description="The mean time spent in the multi-frame escape shared memory buffer for each camera, in nanoseconds"
    )
    stddev_time_spent_in_multi_frame_escape_shm_buffer_ns: float = Field(
        description="The standard deviation of the time spent in the multi-frame escape shared memory buffer for each camera, in nanoseconds"
    )
    mean_time_spent_waiting_to_start_compress_to_jpeg_ns:float = Field(
        description="The mean time spent waiting to start compressing to JPEG for each camera, in nanoseconds"
    )
    stddev_time_spent_waiting_to_start_compress_to_jpeg_ns:float = Field(
        description="The standard deviation of the time spent waiting to start compressing to JPEG for each camera, in nanoseconds"
    )
    mean_time_spent_in_compress_to_jpeg_ns: float = Field(
        description="The mean time spent compressing to JPEG for each camera, in nanoseconds"
    )
    stddev_time_spent_in_compress_to_jpeg_ns: float = Field(
        description="The standard deviation of the time spent compressing to JPEG for each camera, in nanoseconds"
    )

    camera_logs: dict[CameraIdString, CameraTimestampLog] = Field(
        description="Individual CameraTimestampLog objects for each camera in the multi-frame"
    )



    @classmethod
    def from_multi_frame_metadata(
            cls,
            multi_frame_metadata: MultiFrameMetadata,
            initial_multi_frame_payload: MultiFramePayload,
    ):
        camera_timestamp_logs = {
            camera_id: CameraTimestampLog.from_frame_metadata(
                frame_metadata=frame_metadata,
                first_frame_metadata=initial_multi_frame_payload.frames[camera_id].frame_metadata,
                timebase_mapping=initial_multi_frame_payload.timebase_mapping
            )
            for camera_id, frame_metadata in multi_frame_metadata.frame_metadatas.items()}


        timestamps_per_camera_ns = [
            timestamp_log.timestamp_utc_ns
            for timestamp_log in camera_timestamp_logs.values()
        ]
        inter_camera_timestamp_range_ns = np.max(timestamps_per_camera_ns) - np.min(
            timestamps_per_camera_ns
        )
        inter_camera_timestamp_stddev_ns = float(np.std(timestamps_per_camera_ns))

        timestamp_perf_counter_ns = int(np.mean(
            [
                timestamp_log.timestamp_perf_counter_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        ))

        timestamp_from_zero_s = (timestamp_perf_counter_ns- initial_multi_frame_payload.timestamp_ns) / 1e9

        timestamp_utc_ns = int(np.mean(
            [
                timestamp_log.timestamp_utc_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        ))

        timestamp_local_ns = int(np.mean(
            [
                timestamp_log.timestamp_local_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        ))
        timestamp_utc_iso8601 = datetime.fromtimestamp(timestamp_utc_ns / 1e9).isoformat()
        timebase_local_iso8601 = datetime.fromtimestamp(timestamp_local_ns / 1e9).isoformat()

        # Calculate the mean and stddev of the time spent in each stage for each camera frame's lifecycle
        mean_time_before_grab_signal_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_before_grab_signal_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_before_grab_signal_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_before_grab_signal_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_grabbing_frame_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_grabbing_frame_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_grabbing_frame_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_grabbing_frame_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_waiting_to_retrieve_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_waiting_to_retrieve_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_waiting_to_retrieve_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_waiting_to_retrieve_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_retrieving_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_retrieving_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_retrieving_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_retrieving_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_waiting_to_be_put_into_camera_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_waiting_to_be_put_into_camera_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_in_camera_shm_buffer_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_in_camera_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_in_camera_shm_buffer_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_in_camera_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_in_multi_frame_escape_shm_buffer_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_in_multi_frame_escape_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_in_multi_frame_escape_shm_buffer_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_in_multi_frame_escape_shm_buffer_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_waiting_to_start_compress_to_jpeg_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_waiting_to_start_compress_to_jpeg_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_waiting_to_start_compress_to_jpeg_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_waiting_to_start_compress_to_jpeg_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        mean_time_spent_in_compress_to_jpeg_ns = np.mean(
            [
                timestamp_log.frame_lifespan.time_spent_in_compress_to_jpeg_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )
        stddev_time_spent_in_compress_to_jpeg_ns = np.std(
            [
                timestamp_log.frame_lifespan.time_spent_in_compress_to_jpeg_ns
                for timestamp_log in camera_timestamp_logs.values()
            ]
        )

        return cls(
            multi_frame_number=multi_frame_metadata.multi_frame_number,
            timestamp_from_zero_s=timestamp_from_zero_s,
            timestamp_utc_s=timestamp_utc_ns / 1e9,
            timestamp_utc_iso8601=timestamp_utc_iso8601,
            inter_camera_timestamp_range_ns=inter_camera_timestamp_range_ns,
            inter_camera_timestamp_stddev_ns=inter_camera_timestamp_stddev_ns,
            camera_logs=camera_timestamp_logs,
            timestamp_local_iso8601=timebase_local_iso8601,
            mean_time_before_grab_signal_ns=float(mean_time_before_grab_signal_ns),
            stddev_time_before_grab_signal_ns=float(stddev_time_before_grab_signal_ns),
            mean_time_spent_grabbing_frame_ns=float(mean_time_spent_grabbing_frame_ns),
            stddev_time_spent_grabbing_frame_ns=float(stddev_time_spent_grabbing_frame_ns),
            mean_time_waiting_to_retrieve_ns=float(mean_time_waiting_to_retrieve_ns),
            stddev_time_waiting_to_retrieve_ns=float(stddev_time_waiting_to_retrieve_ns),
            mean_time_spent_retrieving_ns=float(mean_time_spent_retrieving_ns),
            stddev_time_spent_retrieving_ns=float(stddev_time_spent_retrieving_ns),
            mean_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns=float(mean_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns),
            stddev_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns=float(stddev_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns),
            mean_time_spent_in_camera_shm_buffer_ns=float(mean_time_spent_in_camera_shm_buffer_ns),
            stddev_time_spent_in_camera_shm_buffer_ns=float(stddev_time_spent_in_camera_shm_buffer_ns),
            mean_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns=float(mean_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns),
            stddev_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns=float(stddev_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns),
            mean_time_spent_in_multi_frame_escape_shm_buffer_ns=float(mean_time_spent_in_multi_frame_escape_shm_buffer_ns),
            stddev_time_spent_in_multi_frame_escape_shm_buffer_ns=float(stddev_time_spent_in_multi_frame_escape_shm_buffer_ns),
            mean_time_spent_waiting_to_start_compress_to_jpeg_ns=float(mean_time_spent_waiting_to_start_compress_to_jpeg_ns),
            stddev_time_spent_waiting_to_start_compress_to_jpeg_ns=float(stddev_time_spent_waiting_to_start_compress_to_jpeg_ns),
            mean_time_spent_in_compress_to_jpeg_ns=float(mean_time_spent_in_compress_to_jpeg_ns),
            stddev_time_spent_in_compress_to_jpeg_ns=float(stddev_time_spent_in_compress_to_jpeg_ns),
        )



    @classmethod
    def to_document(cls) -> str:
        """
        Prints the description of each field in the class in a nice markdown format
        """
        document = "# Main MultiFrame Timestamp Log Field Descriptions:\n"
        document += f"The following fields are included in the main timestamp log, as defined in the {cls.__class__.__name__} data model/class:\n"
        for field_name, field in cls.model_fields.items():
            document += f"- **{field_name}**:\n\n {field.description}\n\n"

        document += "\n\n---\n\n"
        document += CameraTimestampLog.to_document()

        return document

    def to_df_row(self) -> dict[str, int|float|str]:
        """
        Converts the MultiFrameTimestampLog to a list of values for use in a dataframe
        """
        row = {}
        for key_name, field in self.model_fields.items():
            if key_name == "camera_logs":
                continue
            row[key_name] = getattr(self, key_name)
        for camera_id, camera_log in sorted(
            self.camera_logs.items(),
            key=lambda item: item[0],
        ):
            for key_name, field in camera_log.model_fields.items():
                row[f"camera_{camera_id}.{key_name}"] = getattr(camera_log, key_name, None)

        return row
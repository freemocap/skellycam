import logging

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import RecordingInfoMessage, RecordingFinishedMessage
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)

def check_for_new_recording_info(config: CameraConfig,
                                 ipc: CameraGroupIPC,
                                 orchestrator: CameraOrchestrator,
                                 recording_info_subscription: TopicSubscriptionQueue,
                                 self_status: CameraStatus,
                                 video_recorder: VideoRecorder | None,
                                    framerate: float | None = None
                                 ) -> VideoRecorder | None:

    if not recording_info_subscription.empty():
        recording_info_message = recording_info_subscription.get()
        if not isinstance(recording_info_message, RecordingInfoMessage):
            raise RuntimeError(
                f"Expected RecordingInfoMessage for camera {config.camera_id}, "
                f"but received {type(recording_info_message)}"
            )
        recording_info = recording_info_message.recording_info
        if video_recorder is not None:
            logger.info(
                f"New recording info received, closing recording: {video_recorder.recording_info.recording_name} for camera {config.camera_id}")
            finish_recording(ipc=ipc, video_recorder=video_recorder)

        logger.info(
            f"Camera {config.camera_id} creating recorder for recording: {recording_info.recording_name}")
        video_recorder = VideoRecorder.create(
            recording_info=recording_info,
            config=config,
            framerate=framerate
        )
        self_status.recording_in_progress.value = True
        while not orchestrator.all_cameras_recording and ipc.should_continue:
            # Wait for all cameras to be ready to record before starting the recording
            wait_1ms()
    return video_recorder

def finish_recording(ipc: CameraGroupIPC,
                        video_recorder: VideoRecorder) ->  None:
    logger.debug(f"Camera {video_recorder.camera_id} finishing recording: {video_recorder.recording_info.recording_name}")
    frame_metadatas = video_recorder.finish_and_close()
    ipc.pubsub.topics[TopicTypes.RECORDING_FINISHED].publish(RecordingFinishedMessage(
        recording_info=video_recorder.recording_info,
        frame_metadatas=frame_metadatas,
    ))
    video_recorder = None
    return video_recorder 
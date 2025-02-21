import logging
import time

from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO
from skellycam.core.playback.video_group_dto import VideoGroupDTO
from skellycam.core.playback.video_playback import VideoPlayback

logger = logging.getLogger(__name__)

def video_playback_handler(video_group_dto: VideoGroupDTO, 
                        multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO, 
                        ) -> None:
    """
    Interface between the video playback functionality and the app.
    Control happens through the IPC flags, and frames are put in the frame escape ring buffer. 
    This runs in the VideoGroupThread.
    """
    video_configs = video_group_dto.video_configs
    frame_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer = MultiFrameEscapeSharedMemoryRingBuffer.recreate(
        camera_group_dto=video_group_dto,
        shm_dto=multi_frame_escape_shm_dto,
        read_only=False)
    
    current_frame = 0
    with VideoPlayback(video_configs=video_configs) as video_playback:
        while not video_group_dto.ipc_flags.kill_camera_group_flag.value and not video_group_dto.ipc_flags.global_kill_flag.value:
            # TODO: kill camera group flag check might not be right - do we want to be able to run the cameras and videos at the same time?
            if video_group_dto.ipc_flags.playback_stop_flag.value:
                logger.info("Playback stop flag set, stopping video playback.")
                if video_group_dto.ipc_flags.playback_frame_number_flag.value != 0:
                    logger.info("Resetting video playback to frame 0.")
                    video_playback.go_to_frame(0)
                    current_frame = 0
                    video_group_dto.ipc_flags.playback_frame_number_flag.value = 0
                    frame_escape_ring_shm.reset_last_written_indices(0)
                time.sleep(0.30)
                continue
            elif video_group_dto.ipc_flags.playback_pause_flag.value:
                time.sleep(0.30)
                continue
            elif video_group_dto.ipc_flags.playback_frame_number_flag.value != current_frame:
                # TODO: reset shm indices to current frame
                current_frame = video_group_dto.ipc_flags.playback_frame_number_flag.value
                video_playback.go_to_frame(current_frame)
                frame_escape_ring_shm.reset_last_written_indices(current_frame)

            
            frame_escape_ring_shm.put_multi_frame_payload(video_playback.current_payload)
            video_playback.next_frame_payload()
            current_frame += 1
            video_group_dto.ipc_flags.playback_frame_number_flag.value = current_frame
            time.sleep(video_playback.frame_duration)
            
        logger.info("Kill flag recieved, stopping video playback and closing video captures.")
        video_playback.close_video_captures()

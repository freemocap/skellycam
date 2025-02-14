from time import time
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO
from skellycam.core.playback.video_config import VideoConfigs
from skellycam.core.playback.video_group_dto import VideoGroupDTO
from skellycam.core.playback.video_playback import VideoPlayback


def read_video_into_queue(video_group_dto: VideoGroupDTO, 
                        multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO, 
                        ) -> None:
    # TODO respond to flags in loop, including kill flag
    video_configs = video_group_dto.video_configs
    frame_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer = MultiFrameEscapeSharedMemoryRingBuffer.recreate(
        camera_group_dto=video_group_dto,
        shm_dto=multi_frame_escape_shm_dto,
        read_only=False)
    with VideoPlayback(video_configs=video_configs) as video_playback:
        while not video_group_dto.ipc_flags.kill_camera_group_flag.value and not video_group_dto.ipc_flags.global_kill_flag.value:
            if video_playback.playback_stop_flag.value: # TODO: not sure if we want/need this, or if this is correct behavior
                video_playback.close_video_captures()
                break
            if video_group_dto.ipc_flags.playback_pause_flag.value:
                time.sleep(1)
                continue
            
            frame_escape_ring_shm.put_multi_frame_payload(video_playback.current_payload)
            time.sleep(video_playback.frame_duration)
            video_playback.next_frame_payload()

    print("processed entire recording!")
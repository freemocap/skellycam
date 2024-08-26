if record_frames_flag.value:
    is_recording = True

    video_recorder_queue.put(mf_payload)
elif not record_frames_flag.value and is_recording:  # we just stopped recording, need to finish up the video
    is_recording = False
    logger.debug(f"FrameListener - Sending STOP signal to video recorder")
    video_recorder_queue.put(STOP_RECORDING_SIGNAL)

if group_orchestrator.new_frames_available:
    # Skip sending to frontend if we have new frames available to avoid blocking the camera group
    continue

# Pickle and send_bytes, to avoid paying the pickle cost twice when relaying through websocket
frontend_payload = FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf_payload)

frontend_pipe.send_bytes(pickle.dumps(frontend_payload))

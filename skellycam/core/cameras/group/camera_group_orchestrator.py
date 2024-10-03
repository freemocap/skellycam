import multiprocessing
from typing import Dict

from pydantic import BaseModel, SkipValidation, PrivateAttr, Field
from typing_extensions import Annotated

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_triggers import CameraTriggers, logger
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.utilities.wait_functions import wait_10us, wait_1ms, wait_10ms, wait_100ms


class CameraGroupOrchestrator(BaseModel):
    camera_triggers: Dict[CameraId, CameraTriggers]
    new_multi_frame_put_in_shm: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    frame_loop_count: int = -1
    _kill_camera_group_flag: Annotated[multiprocessing.Value, SkipValidation] = PrivateAttr()
    _process_kill_event: Annotated[multiprocessing.Event, SkipValidation] = PrivateAttr()

    pause_when_able: bool = False
    frame_loop_paused: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        self._kill_camera_group_flag = data.get('_kill_camera_group_flag')
        self._process_kill_event = data.get('_process_kill_event')


    @classmethod
    def from_camera_configs(cls,
                            camera_configs: CameraConfigs,
                            kill_camera_group_flag: multiprocessing.Value,
                            process_kill_event: multiprocessing.Event):
        return cls(
            camera_triggers={
                camera_id: CameraTriggers.from_camera_id(camera_id=camera_id,
                                                         kill_camera_group_flag=kill_camera_group_flag)
                for camera_id, camera_config in camera_configs.items()
            },
            _kill_camera_group_flag=kill_camera_group_flag,
            _process_kill_event=process_kill_event
        )

    @property
    def camera_ids(self):
        return list(self.camera_triggers.keys())

    @property
    def should_continue(self):
        return not self._kill_camera_group_flag.value and not self._process_kill_event.is_set()

    @property
    def cameras_ready(self):
        return all([triggers.camera_ready_event.is_set() for triggers in self.camera_triggers.values()])

    @property
    def new_frames_available(self):
        return all([triggers.new_frame_available_trigger.is_set() for triggers in self.camera_triggers.values()])

    @property
    def frames_grabbed(self):
        return not any([triggers.grab_frame_trigger.is_set() for triggers in self.camera_triggers.values()])

    @property
    def frames_retrieved(self):
        return not any([triggers.retrieve_frame_trigger.is_set() for triggers in self.camera_triggers.values()])

    def pause_loop(self):
        self.pause_when_able = True

    def unpause_loop(self):
        self.pause_when_able = False

    ##############################################################################################################
    def trigger_multi_frame_read(self):
        self.frame_loop_count += 1

        if self.pause_when_able:
            logger.trace("Pause requested, pausing frame loop...")
            self.frame_loop_paused = True
            while self.pause_when_able and self.should_continue:
                wait_100ms()
            if self.should_continue:
                logger.trace("Loop unpaused, awaiting cameras ready...")
                self.frame_loop_paused = False
                self.await_for_cameras_ready()

        # 0 - Make sure all cameras are ready
        logger.loop(f"FRAME LOOP #{self.frame_loop_count} BEGIN")
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #0 (start)  - Make sure all cameras are ready")
        self._ensure_cameras_ready()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #0 (finish) - All cameras are ready!")

        # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #1 (start) - Fire grab triggers")
        self._fire_grab_trigger()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #1 (finish) - GRAB triggers fired!")

        # 2 - wait for all cameras to grab a frame
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #2 (start) - Wait for all cameras to GRAB a frame")
        self._await_frames_grabbed()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #2 (finish) - All cameras have GRABbed a frame!")

        # 3- Trigger each camera to retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #3 (start)- Fire retrieve triggers")
        self._fire_retrieve_trigger()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #3 (finish) - RETRIEVE triggers fired!")

        # 4 - wait for all cameras to retrieve the frame and put it in shared memory
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #4 (start) - Wait for new frames to be available")
        self.await_new_frames_available()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #4 (finish) - New frames are available in shared memory!")

        # 5 - Trigger FrameListener to send a multi-frame payload to the FrameRouter
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #5 (start) - Fire escape multi-frame trigger")
        self.new_multi_frame_put_in_shm.set()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #5 (finish) - Escape multi-frame trigger fired!")

        # 6 - wait for the frame to be copied from the `write` buffer to the `read` buffer
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #6 (start) - Wait for multi-frame to be copied from shared memory")
        self._await_mf_copied_from_shm()
        logger.loop(f"**Frame Loop #{self.frame_loop_count}** - Step #6 (finish) - Multi-frame copied from shared memory!")

        # 7 - Make sure all the triggers are as they should be
        logger.loop(
            f"**Frame Loop #{self.frame_loop_count}** - Step# 7 (start) - Verify that everything is hunky-dory after reading the frames")
        self._verify_hunky_dory_after_read()
        logger.loop(
            f"**Frame Loop #{self.frame_loop_count}** - Step #7 (end) - Everything is hunky-dory after reading the frames!")
        logger.loop(f"FRAME LOOP #{self.frame_loop_count} Complete!")

    ##############################################################################################################

    def fire_initial_triggers(self):
        self._ensure_cameras_ready()

        logger.debug(f"Firing initial triggers for all cameras...")
        for triggers in self.camera_triggers.values():
            triggers.initial_trigger.set()

        self._await_initial_triggers_reset()

    def await_for_cameras_ready(self):
        logger.trace("Waiting for all cameras to be ready...")
        while not all([triggers.camera_ready_event.is_set() for triggers in
                       self.camera_triggers.values()]) and self.should_continue:
            wait_10ms()
        logger.debug("All cameras are ready!")

    def await_new_frames_available(self):
        while (not self.frames_retrieved or not self.new_frames_available) and self.should_continue:
            wait_10us()

    def set_multi_frame_pulled_from_shm(self):
        for triggers in self.camera_triggers.values():
            triggers.new_frame_available_trigger.clear()
        self.new_multi_frame_put_in_shm.clear()

    def _await_initial_triggers_reset(self):
        logger.trace("Initial triggers set - waiting for all triggers to reset...")
        while any([triggers.initial_trigger.is_set() for triggers in
                   self.camera_triggers.values()]) and self.should_continue:
            wait_1ms()
        logger.trace("Initial triggers reset - Cameras ready to roll!")

    def _await_frames_grabbed(self):
        while not self.frames_grabbed and self.should_continue:
            wait_10us()

    def _await_mf_copied_from_shm(self):
        while self.new_multi_frame_put_in_shm.is_set() and self.should_continue:
            wait_10us()

    def _fire_grab_trigger(self):
        logger.loop("Triggering all cameras to `grab` a frame...")
        for camera_id, triggers in self.camera_triggers.items():
            triggers.grab_frame_trigger.set()

    def _fire_retrieve_trigger(self):
        logger.loop("Triggering all cameras to `retrieve` that frame...")

        for camera_id, triggers in self.camera_triggers.items():
            triggers.retrieve_frame_trigger.set()

    def _wait_for_frames_grabbed_triggers_reset(self):
        while self.frames_grabbed and self.should_continue:
            wait_10us()

    def _wait_for_retrieve_triggers_reset(self):
        while self.frames_retrieved and self.should_continue:
            wait_10us()

    def _ensure_cameras_ready(self):
        if not self.cameras_ready:
            raise AssertionError("Not all cameras are ready!")

    def _verify_hunky_dory_after_read(self):
        if self.should_continue:
            if not self.cameras_ready:
                raise AssertionError("Not all cameras are ready!")

            if not self.frames_grabbed:
                raise AssertionError("`grab` triggers not reset!")

            if not self.frames_retrieved:
                raise AssertionError("`retrieve` triggers not reset!")

            any_new = any(
                [triggers.new_frame_available_trigger.is_set() for triggers in self.camera_triggers.values()]
            )
            if self.new_frames_available or any_new:
                raise AssertionError(f"New frames available trigger not reset properly? `new_frame_available_trigger`: {self.new_frames_available}, `any_new`: {any_new}")


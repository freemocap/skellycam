import logging
from dataclasses import dataclass

from skellycam.core.camera.camera_worker import CameraWorker, CameraState
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.process_management.process_registry import  ProcessRegistry
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    orchestrator: CameraOrchestrator
    camera_workers: dict[CameraIdString, CameraWorker]

    @property
    def all_ready(self) -> bool:
        return self.orchestrator.all_ready

    @classmethod
    def create(
        cls,
        *,
        ipc: CameraGroupIPC,
        process_registry: ProcessRegistry,
        camera_configs: CameraConfigs,
    ) -> "CameraManager":
        logger.info(f"Starting camera manager process with {len(camera_configs)} cameras")

        camera_statuses: dict[CameraIdString, CameraStatus] = {
            camera_id: CameraStatus() for camera_id in camera_configs.keys()
        }
        orchestrator = CameraOrchestrator.from_statuses(camera_statuses=camera_statuses)

        camera_workers = {
            camera_id: CameraWorker.create(
                camera_id=camera_id,
                ipc=ipc,
                process_registry=process_registry,
                orchestrator=orchestrator,
                config=camera_config,
                update_camera_settings_subscription=ipc.pubsub.topics[
                    TopicTypes.UPDATE_CAMERA_SETTINGS
                ].get_subscription(),
                shm_subscription=ipc.pubsub.topics[
                    TopicTypes.SHM_UPDATES
                ].get_subscription(),
                recording_info_subscription=ipc.pubsub.topics[
                    TopicTypes.RECORDING_INFO
                ].get_subscription(),
            )
            for camera_id, camera_config in camera_configs.items()
        }

        return cls(
            ipc=ipc,
            camera_workers=camera_workers,
            orchestrator=orchestrator,
        )

    def start(self) -> None:
        logger.info("Starting camera processes...")
        for worker in self.camera_workers.values():
            worker.start()

    async def pause_unpause(self, await_state: bool = True) -> None:
        if self.orchestrator.any_cameras_paused:
            await self.unpause(await_unpaused=await_state)
        else:
            await self.pause(await_paused=await_state)

    async def pause(self, await_paused: bool) -> None:
        await self.orchestrator.pause(await_paused=await_paused)

    async def unpause(self, await_unpaused: bool) -> None:
        await self.orchestrator.unpause(await_unpaused=await_unpaused)

    def close(self) -> None:
        logger.info("Closing camera manager and all camera processes...")
        self.ipc.should_continue = False
        self.orchestrator.close()

        for camera_worker in self.camera_workers.values():
            camera_worker.worker.terminate_gracefully()

        self.camera_workers.clear()
        logger.success("Camera manager closed all camera processes successfully.")

    def to_state(self) -> dict[CameraIdString, CameraState]:
        return {
            camera_id: self.camera_workers[camera_id].to_state()
            for camera_id in self.camera_workers
        }

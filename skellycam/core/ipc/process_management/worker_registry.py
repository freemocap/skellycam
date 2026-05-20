import atexit
import logging
import multiprocessing
import multiprocessing.queues
from multiprocessing.sharedctypes import Synchronized
import os
import signal
import threading
import time
from beartype.typing import Callable
from typing import Optional

from skellycam.core.ipc.process_management.managed_worker import (
    ManagedWorker,
    ManagedProcess,
    ManagedThread,
    WorkerMode,
)

logger = logging.getLogger(__name__)


class WorkerRegistry:
    """
    Tracks all ManagedWorker instances (processes or threads), owns the
    parent heartbeat, and ensures clean shutdown.

    The worker_mode flag controls whether create_worker spawns OS processes
    (WorkerMode.PROCESS) or in-process threads (WorkerMode.THREAD).
    """

    def __init__(
        self,
        *,
        global_kill_flag: Synchronized,
        worker_mode: WorkerMode,
    ) -> None:
        self._global_kill_flag = global_kill_flag
        self._worker_mode = worker_mode
        self._heartbeat_timestamp = multiprocessing.Value("d", time.perf_counter())
        self._workers: list[ManagedWorker] = []
        self._heartbeat_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._shutdown_done = False
        atexit.register(self._atexit_cleanup)

    @property
    def worker_mode(self) -> WorkerMode:
        return self._worker_mode

    @property
    def heartbeat_timestamp(self) -> Synchronized:
        """The shared heartbeat value. Pass to CameraGroupIPC so children can monitor parent liveness."""
        return self._heartbeat_timestamp

    def start_heartbeat(self) -> None:
        """Start the heartbeat writer and child monitor threads. Call once after construction."""
        if self._heartbeat_thread is not None:
            raise RuntimeError("Heartbeat already started")
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="WorkerRegistry-Heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()
        logger.debug("Heartbeat thread started")

        self._monitor_thread = threading.Thread(
            target=self._child_monitor_loop,
            name="WorkerRegistry-ChildMonitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.debug("Child monitor thread started")

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.is_set():
            with self._heartbeat_timestamp.get_lock():
                self._heartbeat_timestamp.value = time.perf_counter()
            self._heartbeat_stop.wait(timeout=1.0)

    def _child_monitor_loop(self) -> None:
        """Watch for unexpected worker death and trigger parent shutdown."""
        while not self._heartbeat_stop.is_set():
            for worker in self._workers:
                if (worker.pid is not None
                        and not worker.is_alive()
                        and worker.exitcode not in (None, 0)
                        and not worker._intentionally_terminated):
                    logger.error(
                        f"Worker {worker.name} (PID: {worker.pid}) died with "
                        f"exit code {worker.exitcode} — triggering parent shutdown"
                    )
                    self._global_kill_flag.value = True
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
            self._heartbeat_stop.wait(timeout=1.0)

    def _stop_threads(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

    @property
    def workers(self) -> list[ManagedWorker]:
        return list(self._workers)

    @property
    def alive_workers(self) -> list[ManagedWorker]:
        return [w for w in self._workers if w.is_alive()]

    def create_worker(
        self,
        *,
        target: Callable[..., None],
        name: str,
        log_queue: multiprocessing.queues.Queue | None = None,
        daemon: bool = True,
        kwargs: dict | None = None,
    ) -> ManagedWorker:
        """Create a ManagedWorker (process or thread based on worker_mode), register it, and return it."""
        if self._worker_mode == WorkerMode.PROCESS:
            worker: ManagedWorker = ManagedProcess(
                target=target,
                name=name,
                global_kill_flag=self._global_kill_flag,
                log_queue=log_queue,
                daemon=daemon,
                kwargs=kwargs,
            )
        elif self._worker_mode == WorkerMode.THREAD:
            worker = ManagedThread(
                target=target,
                name=name,
                global_kill_flag=self._global_kill_flag,
                log_queue=log_queue,
                daemon=daemon,
                kwargs=kwargs,
            )
        else:
            raise ValueError(f"Unknown worker mode: {self._worker_mode}")
        self._workers.append(worker)
        return worker

    def shutdown_all(
        self,
        kill_flag_timeout: float = 3.0,
        sigterm_timeout: float = 3.0,
    ) -> None:
        """Shut down all registered workers with escalating force. Safe to call multiple times."""
        if self._shutdown_done:
            return
        self._shutdown_done = True

        self._stop_threads()

        alive = self.alive_workers
        if not alive:
            self._reap_all()
            return

        logger.info(f"WorkerRegistry: shutting down {len(alive)} alive worker(s)")

        # Step 1: kill flag — THIS is the right place to set it (whole-app shutdown)
        self._global_kill_flag.value = True
        for worker in alive:
            worker.join(timeout=kill_flag_timeout)

        # Step 2: terminate stragglers
        still_alive = [w for w in alive if w.is_alive()]
        if still_alive:
            logger.warning(
                f"WorkerRegistry: {len(still_alive)} worker(s) didn't stop via kill flag, "
                f"sending terminate"
            )
            for worker in still_alive:
                worker.terminate()
            for worker in still_alive:
                worker.join(timeout=sigterm_timeout)

        # Step 3: force kill
        still_alive = [w for w in alive if w.is_alive()]
        if still_alive:
            logger.error(
                f"WorkerRegistry: {len(still_alive)} worker(s) didn't respond to terminate, "
                f"sending kill"
            )
            for worker in still_alive:
                worker.kill()
            for worker in still_alive:
                worker.join(timeout=2.0)

        zombies = [w for w in alive if w.is_alive()]
        if zombies:
            raise RuntimeError(
                f"WorkerRegistry: {len(zombies)} worker(s) could not be killed: "
                f"{[f'{w.name}(PID:{w.pid})' for w in zombies]}"
            )

        self._reap_all()
        logger.info("WorkerRegistry: all workers shut down")

    def remove_dead(self) -> list[ManagedWorker]:
        """Remove and reap dead workers from the registry."""
        dead = [w for w in self._workers if not w.is_alive()]
        for w in dead:
            w._reap()
            self._workers.remove(w)
        return dead

    def _reap_all(self) -> None:
        """Join all workers to collect exit status. All must already be dead."""
        unreapable: list[ManagedWorker] = []
        for worker in self._workers:
            worker.join(timeout=1.0)
            if worker.is_alive():
                unreapable.append(worker)
        self._workers.clear()
        if unreapable:
            raise RuntimeError(
                f"_reap_all called but {len(unreapable)} worker(s) are still alive: "
                f"{[f'{w.name}(PID:{w.pid})' for w in unreapable]}"
            )

    def _atexit_cleanup(self) -> None:
        if self._shutdown_done:
            return
        alive = self.alive_workers
        if alive:
            logger.warning(
                f"WorkerRegistry atexit: {len(alive)} worker(s) still alive, forcing shutdown"
            )
            self._global_kill_flag.value = True
            self.shutdown_all(kill_flag_timeout=1.0, sigterm_timeout=1.0)

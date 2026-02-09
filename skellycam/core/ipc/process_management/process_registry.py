import atexit
import logging
import multiprocessing
import os
import signal
import threading
import time
from typing import Callable, Optional

from skellycam.core.ipc.process_management.managed_process import ManagedProcess

logger = logging.getLogger(__name__)


class ProcessRegistry:
    """
    Tracks all ManagedProcess instances, owns the parent heartbeat,
    and ensures clean shutdown. Replaces raw `list[multiprocessing.Process]`.
    """

    def __init__(
        self,
        *,
        global_kill_flag: multiprocessing.Value,
    ) -> None:
        self._global_kill_flag = global_kill_flag
        self._heartbeat_timestamp = multiprocessing.Value("d", time.perf_counter())
        self._processes: list[ManagedProcess] = []
        self._heartbeat_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._shutdown_done = False
        atexit.register(self._atexit_cleanup)

    @property
    def heartbeat_timestamp(self) -> multiprocessing.Value:
        """The shared heartbeat value. Pass to CameraGroupIPC so children can monitor parent liveness."""
        return self._heartbeat_timestamp

    def start_heartbeat(self) -> None:
        """Start the heartbeat writer and child monitor threads. Call once after construction."""
        if self._heartbeat_thread is not None:
            raise RuntimeError("Heartbeat already started")
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="ProcessRegistry-Heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()
        logger.debug("Heartbeat thread started")

        self._monitor_thread = threading.Thread(
            target=self._child_monitor_loop,
            name="ProcessRegistry-ChildMonitor",
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
        """Watch for unexpected child death and trigger parent shutdown."""
        while not self._heartbeat_stop.is_set():
            for proc in self._processes:
                if (proc.pid is not None
                        and not proc.is_alive()
                        and proc.exitcode not in (None, 0)
                        and not proc._intentionally_terminated):
                    logger.error(
                        f"Child process {proc.name} (PID: {proc.pid}) died with "
                        f"exit code {proc.exitcode} — triggering parent shutdown"
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
    def processes(self) -> list[ManagedProcess]:
        return list(self._processes)

    @property
    def alive_processes(self) -> list[ManagedProcess]:
        return [p for p in self._processes if p.is_alive()]

    def create_process(
        self,
        *,
        target: Callable[..., None],
        name: str,
        log_queue: Optional[multiprocessing.Queue] = None,
        daemon: bool = True,
        kwargs: dict | None = None,
    ) -> ManagedProcess:
        """Create a ManagedProcess, register it, and return it. Caller calls .start()."""
        proc = ManagedProcess(
            target=target,
            name=name,
            global_kill_flag=self._global_kill_flag,
            log_queue=log_queue,
            daemon=daemon,
            kwargs=kwargs,
        )
        self._processes.append(proc)
        return proc

    def shutdown_all(
        self,
        kill_flag_timeout: float = 3.0,
        sigterm_timeout: float = 3.0,
    ) -> None:
        """Shut down all registered processes with escalating force. Safe to call multiple times."""
        if self._shutdown_done:
            return
        self._shutdown_done = True

        self._stop_threads()

        alive = self.alive_processes
        if not alive:
            self._reap_all()
            return

        logger.info(f"ProcessRegistry: shutting down {len(alive)} alive process(es)")

        # Step 1: kill flag — THIS is the right place to set it (whole-app shutdown)
        self._global_kill_flag.value = True
        for proc in alive:
            proc.join(timeout=kill_flag_timeout)

        # Step 2: SIGTERM stragglers
        still_alive = [p for p in alive if p.is_alive()]
        if still_alive:
            logger.warning(
                f"ProcessRegistry: {len(still_alive)} process(es) didn't stop via kill flag, "
                f"sending SIGTERM"
            )
            for proc in still_alive:
                proc.terminate()
            for proc in still_alive:
                proc.join(timeout=sigterm_timeout)

        # Step 3: SIGKILL
        still_alive = [p for p in alive if p.is_alive()]
        if still_alive:
            logger.error(
                f"ProcessRegistry: {len(still_alive)} process(es) didn't respond to SIGTERM, "
                f"sending SIGKILL"
            )
            for proc in still_alive:
                proc.kill()
            for proc in still_alive:
                proc.join(timeout=2.0)

        zombies = [p for p in alive if p.is_alive()]
        if zombies:
            raise RuntimeError(
                f"ProcessRegistry: {len(zombies)} process(es) could not be killed: "
                f"{[f'{p.name}(PID:{p.pid})' for p in zombies]}"
            )

        self._reap_all()
        logger.info("ProcessRegistry: all processes shut down")

    def remove_dead(self) -> list[ManagedProcess]:
        """Remove and reap dead processes from the registry."""
        dead = [p for p in self._processes if not p.is_alive()]
        for p in dead:
            p._reap()
            self._processes.remove(p)
        return dead

    def _reap_all(self) -> None:
        """Join all processes to collect exit status. All must already be dead."""
        unreapable: list[ManagedProcess] = []
        for proc in self._processes:
            proc.join(timeout=1.0)
            if proc.is_alive():
                unreapable.append(proc)
        self._processes.clear()
        if unreapable:
            raise RuntimeError(
                f"_reap_all called but {len(unreapable)} process(es) are still alive: "
                f"{[f'{p.name}(PID:{p.pid})' for p in unreapable]}"
            )

    def _atexit_cleanup(self) -> None:
        if self._shutdown_done:
            return
        alive = self.alive_processes
        if alive:
            logger.warning(
                f"ProcessRegistry atexit: {len(alive)} process(es) still alive, forcing shutdown"
            )
            self._global_kill_flag.value = True
            self.shutdown_all(kill_flag_timeout=1.0, sigterm_timeout=1.0)
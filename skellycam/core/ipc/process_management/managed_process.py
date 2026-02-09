"""
ManagedProcess: A multiprocessing.Process subclass that properly handles
shutdown signals, auto-configures child logging, and avoids zombie processes.

Lifecycle state management (should_continue, heartbeat checking) stays in
CameraGroupIPC where the camera loop code actually uses it. ManagedProcess
just handles the process plumbing that was missing from raw mp.Process:
  - SIGTERM/SIGINT handlers in child → sets global_kill_flag
  - Auto child-process logging config (including ws log forwarding)
  - atexit safety net (only fires on unclean exit, not normal camera group close)
  - Escalating shutdown from parent (wait → SIGTERM → SIGKILL, always joins)
"""
import atexit
import logging
import multiprocessing
import os
import signal
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ManagedProcess(multiprocessing.Process):
    """
    Process subclass that installs signal handlers, configures logging,
    and provides escalating shutdown. Drop-in replacement for mp.Process.
    """

    def __init__(
        self,
        *,
        target: Callable[..., None],
        name: str,
        global_kill_flag: multiprocessing.Value,
        log_queue: Optional[multiprocessing.Queue] = None,
        daemon: bool = True,
        kwargs: dict | None = None,
    ) -> None:
        super().__init__(name=name, daemon=daemon)
        self._target_fn: Callable[..., None] = target
        self._global_kill_flag: multiprocessing.Value = global_kill_flag
        self._log_queue: Optional[multiprocessing.Queue] = log_queue
        self._worker_kwargs: dict = kwargs or {}
        self._intentionally_terminated: bool = False

    # ──────────────────────────────────────────────
    # Child-side: runs inside the spawned process
    # ──────────────────────────────────────────────

    def run(self) -> None:
        self._install_signal_handlers()
        self._configure_child_logging()

        _clean_exit = False

        def _atexit_safety_net() -> None:
            if not _clean_exit and not self._global_kill_flag.value:
                logger.warning(
                    f"ManagedProcess {self.name} (PID: {os.getpid()}) "
                    f"exiting uncleanly — setting global kill flag"
                )
                self._global_kill_flag.value = True

        atexit.register(_atexit_safety_net)

        logger.debug(f"ManagedProcess {self.name} (PID: {os.getpid()}) started")

        try:
            self._target_fn(**self._worker_kwargs)
            _clean_exit = True
        except Exception as e:
            logger.exception(
                f"Unhandled exception in ManagedProcess {self.name} "
                f"(PID: {os.getpid()}): {e}"
            )
            self._global_kill_flag.value = True
            raise
        finally:
            logger.debug(f"ManagedProcess {self.name} (PID: {os.getpid()}) exiting")

    def _install_signal_handlers(self) -> None:
        def _on_signal(signum: int, frame: object) -> None:
            sig_name = signal.Signals(signum).name
            logger.info(
                f"ManagedProcess {self.name} (PID: {os.getpid()}) "
                f"received {sig_name}, setting global kill flag"
            )
            self._global_kill_flag.value = True

        signal.signal(signal.SIGTERM, _on_signal)
        signal.signal(signal.SIGINT, _on_signal)

    def _configure_child_logging(self) -> None:
        if self._log_queue is not None:
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL

            configure_logging(LOG_LEVEL, ws_queue=self._log_queue)

    # ──────────────────────────────────────────────
    # Parent-side: called from the parent process
    # ──────────────────────────────────────────────

    def terminate_gracefully(
        self,
        wait_timeout: float = 3.0,
        sigterm_timeout: float = 3.0,
    ) -> None:
        """
        Escalating shutdown for a single process. Always joins to prevent zombies.

        Does NOT touch global_kill_flag — that's the caller's responsibility.
        The caller (CameraManager.close or ProcessRegistry.shutdown_all) already
        told the process to stop via ipc flags or the global kill flag.

        1. Wait for process to exit on its own
        2. Send SIGTERM → wait
        3. Send SIGKILL → wait
        """
        if not self.is_alive():
            self._reap()
            return

        # Mark as intentionally terminated so the child monitor doesn't
        # treat SIGTERM exit codes as crashes
        self._intentionally_terminated = True

        # Step 1: wait — caller already signaled the process to stop
        logger.debug(f"Waiting for {self.name} (PID: {self.pid}) to exit...")
        self.join(timeout=wait_timeout)

        if not self.is_alive():
            logger.debug(f"{self.name} exited cleanly")
            return

        # Step 2: SIGTERM
        logger.warning(f"{self.name} (PID: {self.pid}) didn't exit in time, sending SIGTERM")
        self.terminate()
        self.join(timeout=sigterm_timeout)

        if not self.is_alive():
            logger.debug(f"{self.name} stopped after SIGTERM")
            return

        # Step 3: SIGKILL
        logger.error(f"{self.name} (PID: {self.pid}) didn't respond to SIGTERM, sending SIGKILL")
        self.kill()
        self.join(timeout=2.0)

        if self.is_alive():
            raise RuntimeError(
                f"ManagedProcess {self.name} (PID: {self.pid}) could not be killed!"
            )
        logger.debug(f"{self.name} stopped after SIGKILL")

    def _reap(self) -> None:
        """Join a dead process to reap it and prevent zombie state."""
        try:
            self.join(timeout=1.0)
        except Exception:
            pass
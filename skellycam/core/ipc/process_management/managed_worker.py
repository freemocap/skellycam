"""
ManagedWorker: ABC for managed processes and threads with a common interface.

WorkerMode enum lets callers swap between multiprocessing.Process and
threading.Thread backends. Both provide:
  - Escalating shutdown (wait → terminate → kill, always joins)
  - Unhandled exception → sets global_kill_flag
  - Common interface for pid, exitcode, is_alive, join, start, etc.

ManagedProcess additionally:
  - Installs SIGTERM/SIGINT handlers in child → sets global_kill_flag
  - Auto child-process logging config (including ws log forwarding)
  - atexit safety net (only fires on unclean exit)
  - Queue feeder thread cancellation so processes exit promptly

ManagedThread:
  - Shares parent's logging config (no queue-based logging needed)
  - Cannot be force-killed; terminate/kill set the global_kill_flag
    and rely on the worker function checking it
"""
import abc
import atexit
import logging
import multiprocessing
import os
import signal
import threading
from enum import Enum
from typing import Callable, Optional

from skellycam import LOG_LEVEL
from skellylogs import configure_logging

logger = logging.getLogger(__name__)


class WorkerMode(Enum):
    PROCESS = "process"
    THREAD = "thread"


class ManagedWorker(abc.ABC):
    """
    Common interface for managed processes and threads.
    Drop-in replacement for raw multiprocessing.Process usage.
    """

    def __init__(
        self,
        *,
        name: str,
        global_kill_flag: multiprocessing.Value,
    ) -> None:
        self._name = name
        self._global_kill_flag = global_kill_flag
        self._intentionally_terminated: bool = False

    @property
    def name(self) -> str:
        return self._name

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def is_alive(self) -> bool: ...

    @abc.abstractmethod
    def join(self, timeout: float | None = None) -> None: ...

    @property
    @abc.abstractmethod
    def pid(self) -> int | None: ...

    @property
    @abc.abstractmethod
    def exitcode(self) -> int | None: ...

    @abc.abstractmethod
    def terminate(self) -> None:
        """Request graceful termination. For threads, sets the kill flag."""
        ...

    @abc.abstractmethod
    def kill(self) -> None:
        """Force kill. For threads, this is best-effort (sets kill flag)."""
        ...

    def terminate_gracefully(
        self,
        wait_timeout: float = 3.0,
        sigterm_timeout: float = 3.0,
    ) -> None:
        """
        Escalating shutdown for a single worker. Always joins to prevent
        zombies or leaked threads.

        Does NOT touch global_kill_flag — that's the caller's responsibility.
        The caller (CameraManager.close or WorkerRegistry.shutdown_all)
        already told the worker to stop via ipc flags or the global kill flag.

        1. Wait for worker to exit on its own
        2. terminate() → wait
        3. kill() → wait
        """
        if not self.is_alive():
            self._reap()
            return

        # Mark as intentionally terminated so the child monitor doesn't
        # treat exit codes as crashes
        self._intentionally_terminated = True

        # Step 1: wait — caller already signaled the worker to stop
        logger.debug(f"Waiting for {self.name} (PID: {self.pid}) to exit...")
        self.join(timeout=wait_timeout)

        if not self.is_alive():
            logger.debug(f"{self.name} exited cleanly")
            return

        # Step 2: terminate
        logger.warning(f"{self.name} (PID: {self.pid}) didn't exit in time, sending terminate")
        self.terminate()
        self.join(timeout=sigterm_timeout)

        if not self.is_alive():
            logger.debug(f"{self.name} stopped after terminate")
            return

        # Step 3: kill
        logger.error(f"{self.name} (PID: {self.pid}) didn't respond to terminate, sending kill")
        self.kill()
        self.join(timeout=2.0)

        if self.is_alive():
            raise RuntimeError(
                f"ManagedWorker {self.name} (PID: {self.pid}) could not be stopped!"
            )
        logger.debug(f"{self.name} stopped after kill")

    def _reap(self) -> None:
        """Join a dead worker to clean up resources."""
        try:
            self.join(timeout=1.0)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
# Process implementation
# ══════════════════════════════════════════════════════════════════


def _process_entry_point(
    *,
    target_fn: Callable[..., None],
    name: str,
    global_kill_flag: multiprocessing.Value,
    log_queue: Optional[multiprocessing.Queue],
    worker_kwargs: dict,
) -> None:
    """
    Entry point for child processes. Runs in the spawned process.

    Installs signal handlers, configures logging, runs the target function,
    and sets the global kill flag on unhandled exceptions.
    """

    def _on_signal(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(
            f"ManagedProcess {name} (PID: {os.getpid()}) "
            f"received {sig_name}, setting global kill flag"
        )
        global_kill_flag.value = True

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    if log_queue is not None:
        configure_logging(LOG_LEVEL, ws_queue=log_queue)

    clean_exit = False

    def _atexit_safety_net() -> None:
        if not clean_exit and not global_kill_flag.value:
            logger.warning(
                f"ManagedProcess {name} (PID: {os.getpid()}) "
                f"exiting uncleanly — setting global kill flag"
            )
            global_kill_flag.value = True

    atexit.register(_atexit_safety_net)

    logger.debug(f"ManagedProcess {name} (PID: {os.getpid()}) started")

    try:
        target_fn(**worker_kwargs)
        clean_exit = True
    except Exception as e:
        logger.exception(
            f"Unhandled exception in ManagedProcess {name} "
            f"(PID: {os.getpid()}): {e}"
        )
        global_kill_flag.value = True
        raise
    finally:
        # Cancel queue feeder threads so the process can exit promptly
        # instead of blocking while waiting for pipe buffers to flush.
        if log_queue is not None:
            try:
                log_queue.cancel_join_thread()
            except Exception:
                pass
        logger.debug(f"ManagedProcess {name} (PID: {os.getpid()}) exiting")


class ManagedProcess(ManagedWorker):
    """
    Process-backed worker. Spawns a real OS process via multiprocessing.
    Supports SIGTERM/SIGKILL escalation for force shutdown.
    """

    def __init__(
        self,
        *,
        target: Callable[..., None],
        name: str,
        global_kill_flag: multiprocessing.Value,
        log_queue: Optional[multiprocessing.Queue],
        daemon: bool = True,
        kwargs: dict | None = None,
    ) -> None:
        super().__init__(name=name, global_kill_flag=global_kill_flag)
        self._log_queue = log_queue
        self._process = multiprocessing.Process(
            target=_process_entry_point,
            name=name,
            daemon=daemon,
            kwargs=dict(
                target_fn=target,
                name=name,
                global_kill_flag=global_kill_flag,
                log_queue=log_queue,
                worker_kwargs=kwargs or {},
            ),
        )

    def start(self) -> None:
        self._process.start()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self._process.join(timeout=timeout)

    @property
    def pid(self) -> int | None:
        return self._process.pid

    @property
    def exitcode(self) -> int | None:
        return self._process.exitcode

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()


# ══════════════════════════════════════════════════════════════════
# Thread implementation
# ══════════════════════════════════════════════════════════════════


class ManagedThread(ManagedWorker):
    """
    Thread-backed worker. Runs in a threading.Thread within the parent process.
    Shares the parent's memory space and logging configuration.

    Threads cannot be force-killed. terminate() and kill() set the global
    kill flag; the worker function must check ipc.should_continue or the
    kill flag to exit cooperatively.
    """

    def __init__(
        self,
        *,
        target: Callable[..., None],
        name: str,
        global_kill_flag: multiprocessing.Value,
        log_queue: Optional[multiprocessing.Queue],
        daemon: bool = True,
        kwargs: dict | None = None,
    ) -> None:
        super().__init__(name=name, global_kill_flag=global_kill_flag)
        self._target_fn = target
        self._worker_kwargs = kwargs or {}
        self._exitcode: int | None = None
        self._thread = threading.Thread(
            target=self._run_wrapper,
            name=name,
            daemon=daemon,
        )

    def _run_wrapper(self) -> None:
        logger.debug(f"ManagedThread {self.name} (TID: {threading.get_ident()}) started")
        try:
            self._target_fn(**self._worker_kwargs)
            self._exitcode = 0
        except Exception as e:
            logger.exception(
                f"Unhandled exception in ManagedThread {self.name}: {e}"
            )
            self._exitcode = 1
            self._global_kill_flag.value = True
            raise
        finally:
            logger.debug(f"ManagedThread {self.name} (TID: {threading.get_ident()}) exiting")

    def start(self) -> None:
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout=timeout)

    @property
    def pid(self) -> int | None:
        # Threads share the parent process PID
        return os.getpid()

    @property
    def exitcode(self) -> int | None:
        if self._thread.is_alive():
            return None
        return self._exitcode

    def terminate(self) -> None:
        """Threads cannot receive SIGTERM. Sets the global kill flag instead."""
        logger.debug(
            f"ManagedThread {self.name} cannot be terminated directly, setting kill flag"
        )
        self._global_kill_flag.value = True

    def kill(self) -> None:
        """Threads cannot be force-killed. Sets the global kill flag instead."""
        logger.warning(
            f"ManagedThread {self.name} cannot be force-killed, setting kill flag"
        )
        self._global_kill_flag.value = True

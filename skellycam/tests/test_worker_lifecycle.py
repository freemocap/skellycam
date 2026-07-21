"""Tests for ManagedWorker and WorkerRegistry process/thread lifecycle management."""
import multiprocessing
from multiprocessing.sharedctypes import Synchronized
import time

import pytest

from skellycam.core.ipc.process_management.managed_worker import (
    ManagedProcess,
    ManagedThread,
    ManagedWorker,
    WorkerMode,
)
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry


def _worker_that_exits_cleanly(**kwargs: object) -> None:
    """A worker function that exits immediately."""
    pass


def _worker_that_sleeps(duration: float = 10.0, **kwargs: object) -> None:
    """A worker function that sleeps (simulating a long-running task)."""
    time.sleep(duration)


def _worker_that_raises(**kwargs: object) -> None:
    """A worker function that raises an exception."""
    raise RuntimeError("Intentional test failure")


def _worker_that_respects_kill_flag(
    global_kill_flag: Synchronized,
    **kwargs: object,
) -> None:
    """A worker that checks the kill flag in a loop."""
    while not global_kill_flag.value:
        time.sleep(0.01)


# ---------------------------------------------------------------------------
# ManagedThread
# ---------------------------------------------------------------------------

class TestManagedThread:
    def test_thread_starts_and_exits(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_exits_cleanly,
            name="test-exit",
            global_kill_flag=kill_flag,
            log_queue=None,
        )
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert thread.exitcode == 0

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_thread_exception_sets_kill_flag(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_raises,
            name="test-raise",
            global_kill_flag=kill_flag,
            log_queue=None,
        )
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert thread.exitcode == 1
        assert bool(kill_flag.value) is True

    def test_thread_terminate_sets_kill_flag(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_respects_kill_flag,
            name="test-terminate",
            global_kill_flag=kill_flag,
            log_queue=None,
            kwargs={"global_kill_flag": kill_flag},
        )
        thread.start()
        assert thread.is_alive()

        thread.terminate()  # threads can't be killed, so this sets the flag
        thread.join(timeout=2.0)
        assert bool(kill_flag.value) is True

    def test_thread_pid_is_parent(self) -> None:
        import os
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_exits_cleanly,
            name="test-pid",
            global_kill_flag=kill_flag,
            log_queue=None,
        )
        assert thread.pid == os.getpid()

    def test_thread_name(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_exits_cleanly,
            name="my-thread-name",
            global_kill_flag=kill_flag,
            log_queue=None,
        )
        assert thread.name == "my-thread-name"


# ---------------------------------------------------------------------------
# ManagedWorker.terminate_gracefully
# ---------------------------------------------------------------------------

class TestTerminateGracefully:
    def test_already_dead_worker(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_exits_cleanly,
            name="test-already-dead",
            global_kill_flag=kill_flag,
            log_queue=None,
        )
        thread.start()
        thread.join(timeout=2.0)
        # Should not raise
        thread.terminate_gracefully(wait_timeout=0.5, sigterm_timeout=0.5)

    def test_cooperative_shutdown(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        thread = ManagedThread(
            target=_worker_that_respects_kill_flag,
            name="test-cooperative",
            global_kill_flag=kill_flag,
            log_queue=None,
            kwargs={"global_kill_flag": kill_flag},
        )
        thread.start()
        assert thread.is_alive()

        # Signal the worker to stop
        kill_flag.value = True
        thread.terminate_gracefully(wait_timeout=2.0, sigterm_timeout=1.0)
        assert not thread.is_alive()


# ---------------------------------------------------------------------------
# WorkerRegistry
# ---------------------------------------------------------------------------

class TestWorkerRegistry:
    def test_create_thread_worker(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        worker = registry.create_worker(
            target=_worker_that_exits_cleanly,
            name="test-create",
        )
        assert isinstance(worker, ManagedThread)
        assert worker in registry.workers

    def test_create_process_worker(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.PROCESS,
        )
        worker = registry.create_worker(
            target=_worker_that_exits_cleanly,
            name="test-create-proc",
        )
        assert isinstance(worker, ManagedProcess)

    def test_alive_workers(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        worker = registry.create_worker(
            target=_worker_that_respects_kill_flag,
            name="test-alive",
            kwargs={"global_kill_flag": kill_flag},
        )
        worker.start()
        assert len(registry.alive_workers) == 1

        kill_flag.value = True
        worker.join(timeout=2.0)
        assert len(registry.alive_workers) == 0

    def test_shutdown_all(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        registry.start_heartbeat()

        for i in range(3):
            w = registry.create_worker(
                target=_worker_that_respects_kill_flag,
                name=f"shutdown-test-{i}",
                kwargs={"global_kill_flag": kill_flag},
            )
            w.start()

        assert len(registry.alive_workers) == 3

        registry.shutdown_all(kill_flag_timeout=2.0, sigterm_timeout=1.0)
        assert len(registry.alive_workers) == 0
        assert bool(kill_flag.value) is True

    def test_shutdown_all_idempotent(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        registry.start_heartbeat()

        # Should not raise when called multiple times
        registry.shutdown_all()
        registry.shutdown_all()

    def test_remove_dead(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        w = registry.create_worker(
            target=_worker_that_exits_cleanly,
            name="test-dead",
        )
        w.start()
        w.join(timeout=2.0)

        dead = registry.remove_dead()
        assert len(dead) == 1
        assert w not in registry.workers

    def test_heartbeat_updates_timestamp(self) -> None:
        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        initial_ts = registry.heartbeat_timestamp.value
        registry.start_heartbeat()
        time.sleep(1.5)  # heartbeat updates every 1s
        updated_ts = registry.heartbeat_timestamp.value
        assert updated_ts > initial_ts

        # Clean up
        registry.shutdown_all()

    def test_child_monitor_triggers_shutdown_on_kill_flag(self) -> None:
        """A kill flag set by anyone — with no worker death — must escalate to
        parent shutdown via SIGTERM. This is the path a main-process actor (e.g.
        the websocket relay) relies on: it sets the flag but never exits a worker."""
        import os
        import signal
        from unittest import mock

        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        with mock.patch(
            "skellycam.core.ipc.process_management.worker_registry.os.kill"
        ) as mock_kill:
            registry.start_heartbeat()
            kill_flag.value = True
            # Monitor polls on a ~1s cadence; allow several cycles to observe it.
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline and not mock_kill.called:
                time.sleep(0.05)
            assert mock_kill.called, "monitor did not escalate on a set kill flag"
            mock_kill.assert_called_with(os.getpid(), signal.SIGTERM)

        registry.shutdown_all()

    def test_child_monitor_no_shutdown_when_flag_clear(self) -> None:
        """With the flag clear and all workers healthy, the monitor must NOT
        escalate — guards against a spurious self-SIGTERM."""
        from unittest import mock

        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(
            global_kill_flag=kill_flag,
            worker_mode=WorkerMode.THREAD,
        )
        with mock.patch(
            "skellycam.core.ipc.process_management.worker_registry.os.kill"
        ) as mock_kill:
            registry.start_heartbeat()
            time.sleep(2.5)  # several monitor poll cycles
            assert not mock_kill.called

        registry.shutdown_all()

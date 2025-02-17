import multiprocessing
import logging
import threading
import time

logger = logging.getLogger(__name__)
class NamedKillableProcess(multiprocessing.Process):
    def __init__(self, name: str, global_kill_flag: multiprocessing.Value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self._global_kill_flag = global_kill_flag
        self.kill_flag = multiprocessing.Value("b", False)
        self._kill_listener_thread = threading.Thread(target=self._listen_for_kill_flag)

    def _listen_for_kill_flag(self):
        while not self._global_kill_flag.value and not self.kill_flag.value:
            time.sleep(1)
        logger.info(f"Received kill signal for process: {self.name}")
        time.sleep(2)
        if self.is_alive():
            logger.warning(f"Process {self.name} did not shut down gracefully after kill signal, terminating...")
            self.terminate()

    def start(self):
        logger.info(f"Starting process: {self.name}")
        self._kill_listener_thread.start()
        super().start()

    def stop(self):
        logger.info(f"Stopping process: {self.name}")
        self.kill_flag.value = True
        self.join()

class SkellycamProcessManager:
    def __init__(self, global_kill_flag: multiprocessing.Value):
        self._global_kill_flag = global_kill_flag
        self._processes: dict[str, NamedKillableProcess] = {}

    def create_process(self, name: str, target, args=()):
        logger.info(f"Creating process: {name}")
        self._processes[name] = NamedKillableProcess(name=name, kill_flag=self._global_kill_flag, target=target, args=args)

    def start_process(self, name: str):
        logger.info(f"Starting process: {name}")
        self._processes[name].start()

    def stop_process(self, name: str):
        logger.info(f"Stopping process: {name}")
        self._processes[name].kill_flag.value = True
        self._processes[name].join()

    def join_process(self, name: str):
        logger.info(f"Joining process: {name}")
        self._processes[name].join()
        logger.info(f"Process {name} completed")

    def stop_all_processes(self):
        logger.info(f"Stopping all processes: {self._processes.keys()}")
        for name in self._processes:
            self.stop_process(name)
        logger.info(f"All processes stopped successfully")



SKELLYCAM_PROCESS_MANAGER: SkellycamProcessManager | None = None

def create_skellycam_process_manager(global_kill_flag: multiprocessing.Value) -> SkellycamProcessManager:
    global SKELLYCAM_PROCESS_MANAGER
    if not SKELLYCAM_PROCESS_MANAGER:
        SKELLYCAM_PROCESS_MANAGER = SkellycamProcessManager(global_kill_flag=global_kill_flag)
    return SKELLYCAM_PROCESS_MANAGER

def get_skellycam_process_manager() -> SkellycamProcessManager:
    global SKELLYCAM_PROCESS_MANAGER
    if not SKELLYCAM_PROCESS_MANAGER:
        raise ValueError("Skellycam process manager not initialized!")
    return SKELLYCAM_PROCESS_MANAGER
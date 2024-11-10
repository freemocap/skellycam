

class NamedKillableProcess(multiprocessing.Process):
    def __init__(self, name: str, global_kill_flag: multiprocessing.Value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self._global_kill_flag = global_kill_flag
        self._self_kill_flag = multiprocessing.Value("b", False)


    def _listen_for_kill_flag(self):
        while not self._global_kill_flag.value and not self._self_kill_flag.value:
            time.sleep(1)
        logger.info(f"Received kill signal for process: {self.name}")
        time.sleep(5)
        if self.is_alive():
            logger.warning(f"Process {self.name} did not shut down gracefully after kill signal, terminating...")
            self.terminate()

    def start(self):
        logger.info(f"Starting process: {self.name}")
        self._kill_listener_thread.start()
        super().start()

    def stop(self):
        logger.info(f"Stopping process: {self.name}")
        self._self_kill_flag.value = True
        self.join()

@dataclass
class SkellyCamProcessManager:
    def __init__(self):
        self._global_kill_flag = multiprocessing.Value("b", False)
        self._ipc_flags = IPCFlags(global_kill_flag=self._global_kill_flag)
        self._app_controller = create_skellycam_app_controller(global_kill_flag=self._global_kill_flag)
        self._processes: Dict[str, NamedKillableProcess] = {}

    def create_process(self, name: str, target, args=()):
        self._processes[name] = NamedKillableProcess(name=name, kill_flag=self._global_kill_flag, target=target, args=args)

    def start_process(self, name: str):
        self._processes[name].start()

    def stop_process(self, name: str):
        self._processes[name].kill_flag.value = True
        self._processes[name].join()

    def join_process(self, name: str):
        self._processes[name].join()


SKELLYCAM_PROCESS_MANAGER: SkellyCamProcessManager|None = None

def create_skellycam_process_manager() -> SkellyCamProcessManager:
    global SKELLYCAM_PROCESS_MANAGER
    if not SKELLYCAM_PROCESS_MANAGER:
        SKELLYCAM_PROCESS_MANAGER = SkellyCamProcessManager()
    return SKELLYCAM_PROCESS_MANAGER

def get_skellycam_process_manager() -> SkellyCamProcessManager:
    global SKELLYCAM_PROCESS_MANAGER
    if not SKELLYCAM_PROCESS_MANAGER:
        raise ValueError("Skellycam process manager not initialized!")
    return SKELLYCAM_PROCESS_MANAGER
import multiprocessing

IPC_QUEUE = multiprocessing.Queue()


def get_ipc_queue() -> multiprocessing.Queue:
    return IPC_QUEUE



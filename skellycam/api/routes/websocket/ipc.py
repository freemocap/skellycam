import multiprocessing

IPC_QUEUE = multiprocessing.Queue()


def get_ipc_queue() -> multiprocessing.Queue:
    return IPC_QUEUE


FRONTEND_WS_RELAY_PIPE, FRAME_WRANGLER_PIPE = multiprocessing.Pipe()


def get_frontend_ws_relay_pipe() -> multiprocessing.Pipe:
    return FRONTEND_WS_RELAY_PIPE


def get_frame_wrangler_pipe() -> multiprocessing.Pipe:
    return FRAME_WRANGLER_PIPE

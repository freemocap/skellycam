import multiprocessing

FRONTEND_PIPE_WS_RELAY, FRONTEND_PIPE_FRAME_WRANGLER_CONNECTION = multiprocessing.Pipe()


def get_frontend_pipe_ws_relay_connection():
    return FRONTEND_PIPE_WS_RELAY


def get_frontend_pipe_frame_wrangler_connection():
    return FRONTEND_PIPE_FRAME_WRANGLER_CONNECTION

import logging

import psutil

logger = logging.getLogger(__name__)


def kill_process_on_port(port: int):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['pid'] == 0:
            # Skip kernel processes
            continue
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    logger.warning(
                        f"Process already running on port: {port} (PID:{proc.info['pid']}), shutting it down...[TODO - HANDLE THIS BETTER! Figure out why we're leaving behind zombie processes...]")
                    proc.kill()
        except psutil.AccessDenied:
            continue


if __name__ == "__main__":
    from skellycam.api.server.server_constants import PORT

    kill_process_on_port(PORT)

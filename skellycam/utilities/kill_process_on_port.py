import logging
import socket

import psutil


logger = logging.getLogger(__name__)


def kill_process_on_port(port: int) -> None:
    # Fast path: skip expensive psutil scan if nothing is listening on the port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        if s.connect_ex(('127.0.0.1', port)) != 0:
            logger.debug(f"Port {port} is free, skipping process scan")
            return

    logger.warning(f"Port {port} is in use — scanning for process to kill...")
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
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue


if __name__ == "__main__":
    from skellycam.api.server_constants import PORT
    kill_process_on_port(PORT)

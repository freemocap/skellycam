import logging
import socket

logger = logging.getLogger(__name__)


def find_available_port(start_port: int) -> int:
    logger.debug(f"Finding available port starting at {start_port}")
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            logger.debug(f"Trying port {port}...")
            try:
                s.bind(("localhost", port))
                logger.debug(f"Port {port} is available!")
                return port
            except socket.error as e:
                logger.debug(f"Port {port} is not available: `{e}`")
                port += 1
                if port > 65535:  # No more ports available
                    logger.error("No ports available!")
                    raise e

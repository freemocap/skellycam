import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_empty_directories(base_path: str) -> None:
    logger.debug(f"Cleaning up empty directories...")
    for directory in reversed(list(Path(base_path).glob("**"))):
        if directory.is_dir():
            try:
                directory.rmdir()  # Remove directories
            except OSError:
                pass  # Directory not empty, can't be removed

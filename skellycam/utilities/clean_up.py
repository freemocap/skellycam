from skellycam.system.environment.get_logger import logger
from skellycam.system.environment.default_paths import get_default_skellycam_base_folder_path


def remove_empty_directories():
    logger.debug(f"Cleaning up empty directories...")
    base_path = get_default_skellycam_base_folder_path()
    for directory in reversed(list(base_path.glob('**'))):
        if directory.is_dir():
            try:
                directory.rmdir()  # Remove directories
            except OSError:
                pass  # Directory not empty, can't be removed

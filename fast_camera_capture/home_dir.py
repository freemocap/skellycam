from pathlib import Path


def os_independent_home_dir():
    return str(Path.home())

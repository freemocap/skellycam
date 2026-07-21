"""
Pre-compile all skellycam .py files to .pyc bytecode.

On Windows, multiprocessing.spawn causes each child process to re-import
the full module tree. If .pyc files are missing or stale, Python reads
the .py source, compiles it, and writes a .pyc — all of which involve
file I/O that can race with other children and antivirus scanners.

Pre-compiling guarantees that every import hits a single .pyc read
with no source file access and no write, cutting per-module I/O in half
and eliminating the file-locking race.

compileall already skips files whose .pyc is newer than the .py source,
so calling this on every startup is cheap (~50ms when nothing changed).
"""
import compileall
import logging
import sys
import time
from pathlib import Path

import skellycam

logger = logging.getLogger(__name__)

_PACKAGE_DIR = str(Path(skellycam.__file__).parent)


def ensure_bytecode_compiled() -> None:
    """Pre-compile all skellycam .py → .pyc, skipping unchanged files.

    Only runs on Windows where multiprocessing.spawn makes this necessary.
    Uses timestamp-based invalidation (the default) so stale .pyc files
    from edited source files are automatically recompiled.
    """
    if sys.platform != "win32":
        return
    if getattr(sys, "frozen", False):
        # we're probably running from a pyinstaller-like compiled binary, skip this biz!
        return

    t_start = time.perf_counter()
    success = compileall.compile_dir(
        _PACKAGE_DIR,
        quiet=2,
        workers=0,  # 0 = use all available CPUs for parallel compilation
        invalidation_mode=None,  # default: timestamp-based, recompiles when .py is newer
    )
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    if not success:
        raise RuntimeError(
            f"Failed to compile bytecode for {_PACKAGE_DIR} — "
            f"check for syntax errors in .py files"
        )

    logger.debug(f"Bytecode compilation check completed in {elapsed_ms:.0f}ms")
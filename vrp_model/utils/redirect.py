"""Redirect process-level stdout/stderr (including native C/C++ output) to a file."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import IO, Any


def fileno(file_or_fd: IO[Any] | int) -> int:
    """Return the OS file descriptor of a file object, or ``file_or_fd`` itself if already one."""
    fd = getattr(file_or_fd, "fileno", lambda: file_or_fd)()
    if not isinstance(fd, int):
        raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
    return fd


@contextmanager
def stdout_redirected(to: IO[Any], stdout: IO[Any] | None = None) -> Generator[IO[Any]]:
    """Send everything written to ``stdout`` (default ``sys.stdout``) into ``to``.

    When ``stdout`` exposes a real file descriptor, it is ``dup2``-ed onto ``to`` so output from
    native libraries (e.g. OR-Tools' C++ logger) is captured too. Otherwise (e.g. notebooks),
    only Python-level writes are patched.
    """
    if stdout is None:
        stdout = sys.stdout
    try:
        stdout_fd = fileno(stdout)
    except (ValueError, OSError):
        patched: Any = stdout
        original_write = patched.write

        def new_write(data: str) -> int:
            n = to.write(data)
            to.flush()
            return n

        patched.write = new_write
        try:
            yield stdout
        finally:
            patched.write = original_write
        return

    # copy stdout_fd before it is overwritten
    with os.fdopen(os.dup(stdout_fd), "wb") as copied:
        stdout.flush()  # flush library buffers that dup2 knows nothing about
        to.flush()
        os.dup2(fileno(to), stdout_fd)
        try:
            yield stdout
        finally:
            # restore stdout to its previous value
            stdout.flush()
            os.dup2(copied.fileno(), stdout_fd)

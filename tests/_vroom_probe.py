"""Shared VROOM / pyvroom matrix probe for skipping tests when matrices fail to load."""


def vroom_matrix_ok() -> bool:
    """Return True if pyvroom accepts a minimal duration matrix on this platform."""
    try:
        import numpy as np
        import vroom
    except ModuleNotFoundError:
        return False
    try:
        inp = vroom.Input()
        m = np.require(
            np.ascontiguousarray([[0, 1], [1, 0]], dtype=np.uint32),
            dtype=np.uint32,
            requirements=["C"],
        )
        inp.set_durations_matrix("car", m)
    except RuntimeError:
        return False
    return True

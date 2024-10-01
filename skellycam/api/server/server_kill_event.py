import multiprocessing
from typing import Optional

KILL_EVENT: Optional[multiprocessing.Event] = None


def set_kill_event(event: multiprocessing.Event):
    global KILL_EVENT
    KILL_EVENT = event


def get_kill_event() -> multiprocessing.Event:
    global KILL_EVENT
    if KILL_EVENT is None:
        raise ValueError("Kill event not set")
    return KILL_EVENT

"""Keep Windows awake while a rented instance runs, without changing any power setting.

``SetThreadExecutionState`` asks Windows not to sleep for as long as the calling thread
holds the request. The request ends when the process exits, so a crashed controller never
leaves the machine pinned awake. On other systems these calls do nothing.
"""
import ctypes
import os

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def hold():
    """Ask Windows to stay awake. Returns True when the request was accepted."""
    if os.name != 'nt':
        return False
    previous = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    return previous != 0


def release():
    """Drop the request made by ``hold``."""
    if os.name != 'nt':
        return False
    return ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS) != 0

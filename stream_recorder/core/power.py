"""Keep the machine awake while a recording is armed or running.

A job is often set up the night before, so the app may sit armed for 12+ hours.
If the machine sleeps, the scheduled recording silently never happens.
"""

import subprocess
import sys

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


class KeepAwake:
    """Blocks system sleep between hold() and release(). Safe to call twice."""

    def __init__(self):
        self._held = False
        self._caffeinate: subprocess.Popen | None = None

    def hold(self) -> None:
        if self._held:
            return

        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
            )
        elif sys.platform == "darwin":
            self._caffeinate = subprocess.Popen(
                ["caffeinate", "-i", "-s"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        self._held = True

    def release(self) -> None:
        if not self._held:
            return

        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        elif self._caffeinate is not None:
            self._caffeinate.terminate()
            self._caffeinate = None

        self._held = False

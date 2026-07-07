import ctypes
from ctypes import windll, c_uint, byref

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

# WTS session states
_WTS_ACTIVE = 0
_WTS_DISCONNECTED = 4

# GetUserNameW buffer size
_MAX_USERNAME = 256


def _get_active_username() -> str | None:
    """Return the username of the currently active console session, or None if unavailable."""
    try:
        import win32api  # type: ignore
        import win32con  # type: ignore
        import win32ts   # type: ignore

        sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for s in sessions:
            if s["State"] == _WTS_ACTIVE and s["SessionId"] != 0:
                try:
                    username = win32ts.WTSQuerySessionInformation(
                        win32ts.WTS_CURRENT_SERVER_HANDLE,
                        s["SessionId"],
                        win32ts.WTSUserName,
                    )
                    if username:
                        return username
                except Exception:
                    continue
        return None
    except Exception as e:
        get_logger().warning("Failed to read session info: %s", e)
        return None


def _is_session_locked() -> bool:
    """Return True if the current desktop session is locked."""
    try:
        # OpenInputDesktop returns None/0 when the secure desktop (lock screen) is active
        h_desktop = windll.user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_READOBJECTS
        if not h_desktop:
            return True
        windll.user32.CloseDesktop(h_desktop)
        return False
    except Exception:
        return False


class SessionMonitor(BaseMonitor):
    """Reports the logged-on Windows username and whether the session is locked."""

    def read(self) -> list[MetricSnapshot]:
        username = _get_active_username()
        locked = _is_session_locked()

        if username:
            display = f"{username} (Locked)" if locked else username
        else:
            display = "None"

        return [
            MetricSnapshot(
                label="Logged On",
                value=0,
                unit="",
                threshold=None,
                display_value=display,
            ),
        ]

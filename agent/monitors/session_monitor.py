import ctypes
from ctypes import windll, c_ulong, byref

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

_WTS_ACTIVE = 0

windll.kernel32.ProcessIdToSessionId.restype = ctypes.c_bool
windll.kernel32.ProcessIdToSessionId.argtypes = [c_ulong, ctypes.POINTER(c_ulong)]
windll.kernel32.WTSGetActiveConsoleSessionId.restype = c_ulong


def _get_active_session_id() -> int | None:
    session_id = windll.kernel32.WTSGetActiveConsoleSessionId()
    return None if session_id == 0xFFFFFFFF else int(session_id)


def _get_active_username() -> str | None:
    try:
        import win32ts  # type: ignore
        session_id = _get_active_session_id()
        if session_id is None:
            return None
        username = win32ts.WTSQuerySessionInformation(
            win32ts.WTS_CURRENT_SERVER_HANDLE,
            session_id,
            win32ts.WTSUserName,
        )
        return username or None
    except Exception as e:
        get_logger().warning("Failed to read session username: %s", e)
        return None


def _is_session_locked() -> bool:
    """
    Check for LockApp.exe (lock screen host) or LogonUI.exe (credential UI) running
    in the active console session. LockApp.exe is present from Win+L onwards;
    LogonUI.exe appears when the credential prompt is shown. Checking both covers
    the full lock lifecycle reliably from an elevated background process.
    """
    try:
        import psutil  # type: ignore

        session_id = _get_active_session_id()
        if session_id is None:
            return False

        for proc in psutil.process_iter(["name", "pid"]):
            if proc.info["name"].lower() not in ("lockapp.exe", "logonui.exe"):
                continue
            try:
                proc_session = c_ulong(0)
                ok = windll.kernel32.ProcessIdToSessionId(
                    c_ulong(proc.info["pid"]),
                    byref(proc_session),
                )
                if ok and proc_session.value == session_id:
                    return True
            except Exception:
                continue

        return False
    except Exception as e:
        get_logger().warning("Failed to check lock state: %s", e)
        return False


class SessionMonitor(BaseMonitor):
    """Reports the logged-on Windows username and lock state."""

    def read(self) -> list[MetricSnapshot]:
        username = _get_active_username()
        locked = _is_session_locked()

        if username:
            display = f"{username} (Locked)" if locked else username
        else:
            display = "None"

        return [MetricSnapshot(
            label="Logged On",
            value=0,
            unit="",
            threshold=None,
            display_value=display,
        )]

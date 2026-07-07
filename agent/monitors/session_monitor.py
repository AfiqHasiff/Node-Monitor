import psutil

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

_WTS_ACTIVE = 0


def _get_active_username() -> str | None:
    try:
        import win32ts  # type: ignore
        sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for s in sessions:
            if s["State"] != _WTS_ACTIVE or s["SessionId"] == 0:
                continue
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
        get_logger().warning("Failed to read session username: %s", e)
        return None


def _is_session_locked() -> bool:
    """
    Detect lock screen by checking for LogonUI.exe in the active console session.
    Windows spawns LogonUI.exe in the user's session when the screen is locked and
    terminates it on unlock. Reliable from elevated/background processes.
    """
    try:
        import win32ts    # type: ignore
        import win32con   # type: ignore

        session_id = None
        sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for s in sessions:
            if s["State"] == _WTS_ACTIVE and s["SessionId"] != 0:
                session_id = s["SessionId"]
                break

        if session_id is None:
            return False

        for proc in psutil.process_iter(["name", "pid"]):
            if proc.info["name"].lower() != "logonui.exe":
                continue
            try:
                import win32process  # type: ignore
                import win32api      # type: ignore
                handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, proc.info["pid"])
                proc_session = win32process.GetProcessId(handle)
                win32api.CloseHandle(handle)
                if proc_session == session_id:
                    return True
            except Exception:
                # If we can't query the session, assume it's in the right session
                return True

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

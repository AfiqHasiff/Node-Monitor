from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

# WTS session states
_WTS_ACTIVE = 0

# WTSSessionInfoEx lock states
_WTS_SESSIONSTATE_LOCK = 0
_WTS_SESSIONSTATE_UNLOCK = 1


def _get_session_info() -> tuple[str | None, bool]:
    """
    Return (username, is_locked) for the active console session.
    Uses WTSQuerySessionInformationW with WTSSessionInfoEx (25) to get lock state —
    this works correctly from background/elevated processes unlike OpenInputDesktop.
    """
    try:
        import win32ts  # type: ignore

        sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for s in sessions:
            if s["State"] != _WTS_ACTIVE or s["SessionId"] == 0:
                continue

            session_id = s["SessionId"]

            try:
                username = win32ts.WTSQuerySessionInformation(
                    win32ts.WTS_CURRENT_SERVER_HANDLE,
                    session_id,
                    win32ts.WTSUserName,
                )
            except Exception:
                username = None

            # WTSSessionInfoEx (value 25) returns a WTSINFOEX struct with lock state
            try:
                info = win32ts.WTSQuerySessionInformation(
                    win32ts.WTS_CURRENT_SERVER_HANDLE,
                    session_id,
                    25,  # WTSSessionInfoEx
                )
                # info is a dict: {"Level": 1, "Data": {"SessionFlags": ...}}
                session_flags = info.get("Data", {}).get("SessionFlags", _WTS_SESSIONSTATE_UNLOCK)
                locked = session_flags == _WTS_SESSIONSTATE_LOCK
            except Exception:
                locked = False

            return username or None, locked

        return None, False
    except Exception as e:
        get_logger().warning("Failed to read session info: %s", e)
        return None, False


class SessionMonitor(BaseMonitor):
    """Reports the logged-on Windows username and whether the session is locked."""

    def read(self) -> list[MetricSnapshot]:
        username, locked = _get_session_info()

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

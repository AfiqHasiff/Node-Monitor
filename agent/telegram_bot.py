from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

from agent.base_monitor import MetricSnapshot
from agent.logger import get_logger

_ALERT_EMOJI = {
    "CPU Temp": "🔥",
    "GPU Temp": "🔥",
    "CPU Usage": "⚡",
    "GPU Usage": "⚡",
    "GPU VRAM": "💾",
    "Idle Time": "⚠️",
}

StatusCallback = Callable[[], Awaitable[list[MetricSnapshot]]]

_MV2 = 2  # MarkdownV2 version constant for escape_markdown


def _esc(text: str) -> str:
    return escape_markdown(str(text), version=_MV2)


def _format_alert(snapshot: MetricSnapshot) -> str:
    emoji = _ALERT_EMOJI.get(snapshot.label, "⚠️")
    return (
        f"{emoji} *{_esc(snapshot.label)} Alert*\n\n"
        f"Current: {_esc(snapshot.value)}{_esc(snapshot.unit)}\n"
        f"Threshold: {_esc(snapshot.threshold)}{_esc(snapshot.unit)}"
    )


def _format_status(snapshots: list[MetricSnapshot]) -> str:
    lines = ["🖥 *Node Status*\n"]
    any_warning = False

    for s in snapshots:
        if s.label == "Idle Time":
            total_minutes = int(s.value)
            hours, minutes = divmod(total_minutes, 60)
            display = f"{hours}h {minutes}m" if hours else f"{minutes}m"
        else:
            display = f"{s.value}{s.unit}"

        if s.threshold and s.value > s.threshold:
            any_warning = True

        lines.append(f"`{s.label:<12}` {_esc(display)}")

    status_line = "⚠️ WARNING" if any_warning else "✅ Healthy"
    lines.append(f"\nStatus: {status_line}")
    return "\n".join(lines)


class TelegramBot:
    def __init__(self, bot_token: str, chat_id: str, status_callback: StatusCallback):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._status_callback = status_callback
        self._app: Application | None = None

    async def start(self) -> None:
        self._app = Application.builder().token(self._bot_token).build()
        self._app.add_handler(CommandHandler("status", self._handle_status))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        get_logger().info("Telegram bot started")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send_alert(self, snapshot: MetricSnapshot) -> None:
        if self._app is None:
            return
        try:
            await self._app.bot.send_message(
                chat_id=self._chat_id,
                text=_format_alert(snapshot),
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            get_logger().error("Failed to send Telegram alert: %s", e)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        snapshots = await self._status_callback()
        text = _format_status(snapshots)
        await update.message.reply_text(text, parse_mode="MarkdownV2")

from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

from agent.base_monitor import MetricSnapshot
from agent.logger import get_logger

StatusCallback = Callable[[], Awaitable[list[MetricSnapshot]]]

_MV2 = 2


def _esc(text: str) -> str:
    return escape_markdown(str(text), version=_MV2)


def _render_snapshot(s: MetricSnapshot, breached: bool) -> str:
    display = s.display_value if s.display_value else f"{s.value}{s.unit}"
    if s.threshold:
        t = s.threshold_display if s.threshold_display else f"{s.threshold}{s.unit}"
        display = f"{display} / {t}"
    badge = "  ⚠️" if breached else ""
    return f"`{s.label:<12}` {_esc(display)}{badge}"


def _format_message(header: str, snapshots: list[MetricSnapshot]) -> str:
    lines = [f"{header}\n"]
    for s in snapshots:
        breached = bool(s.threshold) and s.value > s.threshold
        lines.append(_render_snapshot(s, breached))
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

    async def send_alert(self, snapshots: list[MetricSnapshot]) -> None:
        """Send one combined alert message for all currently-breached metrics."""
        if self._app is None:
            return
        text = _format_message("⚠️ *Threshold Alert*", snapshots)
        try:
            await self._app.bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            get_logger().error("Failed to send Telegram alert: %s", e)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        snapshots = await self._status_callback()
        text = _format_message("🖥 *Node Status*", snapshots)
        await update.message.reply_text(text, parse_mode="MarkdownV2")

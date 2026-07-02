"""Messaging — Slack primary, email fallback."""

import os

from tools.slack import send_dm, send_channel_message
from tools.slack import notify_manager as slack_notify_manager
from tools.email_service import send_helpdesk_email

MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "it-manager@company.com")
DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "#general")


def send_user_message(email: str, message: str) -> dict:
    result = send_dm(email, message)
    if result["status"] == "sent":
        return result
    return send_helpdesk_email(
        to_email=email,
        subject="IT Helpdesk Notification",
        body_html=f"<p>{message}</p>",
    )


def notify_manager(message: str, priority: str = "P3") -> dict:
    result = slack_notify_manager(message, priority)
    if result["status"] == "sent":
        return result
    return send_helpdesk_email(
        to_email=MANAGER_EMAIL,
        subject=f"[SLA Breach] {priority} — urgent attention",
        body_html=f"<p>{message}</p>",
    )


def notify_channel(channel: str | None = None, message: str = "") -> dict:
    target = channel or DEFAULT_CHANNEL
    result = send_channel_message(target, message)
    if result["status"] == "sent":
        return result
    return send_helpdesk_email(
        to_email=MANAGER_EMAIL,
        subject=f"[Alert] {target}",
        body_html=f"<p>{message}</p>",
    )

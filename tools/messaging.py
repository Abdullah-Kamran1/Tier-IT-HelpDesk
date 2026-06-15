"""Stub messaging tool functions for user and manager notifications."""


def send_user_message(email: str, message: str) -> dict:
    return {
        "email": email,
        "message": message,
        "sent": True,
        "channel": "email",
        "source": "stub",
    }


def notify_manager(message: str, priority: str = "P3") -> dict:
    return {
        "recipient": "it-manager",
        "message": message,
        "priority": priority,
        "sent": True,
        "channel": "slack",
        "source": "stub",
    }


def notify_channel(channel: str, message: str) -> dict:
    return {
        "channel": channel,
        "message": message,
        "sent": True,
        "source": "stub",
    }

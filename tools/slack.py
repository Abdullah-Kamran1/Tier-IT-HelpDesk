"""Slack notification tool using the Slack Web API SDK."""
import os

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    _slack_available = True
except ImportError:
    _slack_available = False

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_MANAGER_USER_ID = os.getenv("SLACK_MANAGER_USER_ID")
SLACK_MANAGER_CHANNEL = os.getenv("SLACK_MANAGER_CHANNEL", "#it-alerts")

_client = None


def _get_client() -> "WebClient | None":
    global _client
    if _client is None and _slack_available and SLACK_BOT_TOKEN:
        _client = WebClient(token=SLACK_BOT_TOKEN)
    return _client


def send_dm(user_id: str, message: str) -> dict:
    """Send a direct message to a Slack user by their user ID."""
    client = _get_client()
    if client is None:
        return {"status": "failed", "provider": "slack", "error": "SLACK_BOT_TOKEN not configured or slack-sdk not installed"}
    try:
        response = client.chat_postMessage(channel=user_id, text=message)
        return {
            "status": "sent",
            "provider": "slack",
            "channel": user_id,
            "ts": response.get("ts"),
        }
    except SlackApiError as e:
        return {"status": "failed", "provider": "slack", "error": str(e)}


def send_channel_message(channel: str, message: str) -> dict:
    """Post a message to a Slack channel."""
    client = _get_client()
    if client is None:
        return {"status": "failed", "provider": "slack", "error": "SLACK_BOT_TOKEN not configured or slack-sdk not installed"}
    try:
        response = client.chat_postMessage(channel=channel, text=message)
        return {
            "status": "sent",
            "provider": "slack",
            "channel": channel,
            "ts": response.get("ts"),
        }
    except SlackApiError as e:
        return {"status": "failed", "provider": "slack", "error": str(e)}


def notify_manager(message: str, priority: str = "P3") -> dict:
    """Send a priority alert to the IT manager via Slack DM, with channel fallback."""
    formatted = f"[{priority}] {message}"
    if SLACK_MANAGER_USER_ID:
        result = send_dm(SLACK_MANAGER_USER_ID, formatted)
        if result["status"] == "sent":
            return result
    return send_channel_message(SLACK_MANAGER_CHANNEL, formatted)

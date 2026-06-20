"""Tests for the Resend email notification service."""  # noqa: INP001
from unittest.mock import patch

import pytest

from tools.email_service import (
    FROM_ADDRESS,
    send_helpdesk_email,
    send_mfa_enrollment_email,
    send_mfa_reset_notification,
    send_password_reset_email,
)


def test_send_helpdesk_email_dispatches():
    with patch("tools.email_service.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "email_abc123"}

        result = send_helpdesk_email("user@example.com", "Test Subject", "<p>Hello</p>")

    assert result["status"] == "dispatched"
    assert result["provider"] == "resend"
    assert result["id"] == "email_abc123"

    mock_send.assert_called_once()
    params = mock_send.call_args[0][0]
    assert params["to"] == ["user@example.com"]
    assert params["subject"] == "Test Subject"
    assert params["html"] == "<p>Hello</p>"
    assert params["from"] == FROM_ADDRESS


def test_send_helpdesk_email_handles_api_error():
    with patch("tools.email_service.resend.Emails.send") as mock_send:
        mock_send.side_effect = Exception("API rate limit exceeded")

        result = send_helpdesk_email("user@example.com", "Subject", "<p>Body</p>")

    assert result["status"] == "failed"
    assert "rate limit" in result["error"].lower()


def test_send_helpdesk_email_fails_gracefully_when_resend_missing():
    with patch("tools.email_service._resend_available", False):
        result = send_helpdesk_email("user@example.com", "Subject", "<p>Body</p>")

    assert result["status"] == "failed"
    assert "not installed" in result["error"]


def test_send_mfa_enrollment_email_builds_html():
    with patch("tools.email_service.send_helpdesk_email") as mock_send:
        mock_send.return_value = {"status": "dispatched", "id": "email_1"}

        result = send_mfa_enrollment_email("user@example.com", "https://example.com/enroll")

    assert result["status"] == "dispatched"

    mock_send.assert_called_once()
    args = mock_send.call_args[0]
    assert args[0] == "user@example.com"
    assert "Multi-Factor Authentication" in args[1]
    assert "https://example.com/enroll" in args[2]
    assert "user@example.com" in args[2]


def test_send_mfa_enrollment_email_has_cta_button():
    with patch("tools.email_service.send_helpdesk_email") as mock_send:

        send_mfa_enrollment_email("user@example.com", "https://example.com/enroll")

    html = mock_send.call_args[0][2]
    assert "Enroll in MFA" in html
    assert 'href="https://example.com/enroll"' in html


def test_send_password_reset_email_includes_security_warning():
    with patch("tools.email_service.send_helpdesk_email") as mock_send:

        send_password_reset_email("user@example.com")

    html = mock_send.call_args[0][2]
    assert "Password Reset" in html
    assert "may be compromised" in html


def test_send_mfa_reset_notification_informs_user():
    with patch("tools.email_service.send_helpdesk_email") as mock_send:

        send_mfa_reset_notification("user@example.com")

    args = mock_send.call_args[0]
    assert args[0] == "user@example.com"
    assert "MFA Reset" in args[1]
    assert "re-enroll" in args[2].lower()


def test_send_mfa_reset_notification_security_warning():
    with patch("tools.email_service.send_helpdesk_email") as mock_send:

        send_mfa_reset_notification("user@example.com")

    html = mock_send.call_args[0][2]
    assert "may be compromised" in html


def test_dry_run_send_helpdesk_email_no_mock():
    result = send_helpdesk_email(
        "dry-run@example.com",
        "[DRY RUN] Test",
        "<p>This is a dry run — no real API call expected.</p>",
    )
    assert result["status"] in ("dispatched", "failed")

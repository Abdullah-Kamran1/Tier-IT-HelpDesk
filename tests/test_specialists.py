from unittest.mock import patch

import pytest

from agents import comms_productivity, identity_access
from schemas.classification import ClassificationResult
from schemas.specialist import SpecialistResult


def _fake_user(user_id="auth0|123", email="user@example.com"):
    return type("FakeUser", (), {"user_id": user_id, "email": email})()


def _classification(ticket_type: str, route_to: str, suspicious_flags=None):
    return ClassificationResult(
        ticket_type=ticket_type,
        priority="P3",
        tier1_capable=True,
        route_to=route_to,
        confidence=0.95,
        suspicious_flags=suspicious_flags or [],
        duplicate_signal=False,
        split_routes=None,
        escalate_reason=None,
        classification_notes="test",
        sla_hours=8,
        source_id=None,
    )


def _handle_with_auth0(ticket_text, classification, metadata):
    with (
        patch("agents.identity_access.get_user_by_email") as mock_get,
        patch("agents.identity_access.trigger_password_reset") as mock_reset,
        patch("agents.identity_access.delete_mfa_enrollments") as mock_mfa,
        patch("agents.identity_access.send_password_reset_email") as mock_email_pw,
        patch("agents.identity_access.send_mfa_reset_notification") as mock_email_mfa,
        patch("agents.identity_access.send_mfa_enrollment_email") as mock_email_enroll,
    ):
        mock_get.return_value = [_fake_user()]
        mock_reset.return_value = {"status": "reset_sent"}
        mock_mfa.return_value = {"status": "mfa_reset", "deleted_factors": ["guardian"]}
        return identity_access.handle(ticket_text, classification, metadata)


@pytest.mark.parametrize(
    ("ticket_type", "text", "expected_tag"),
    [
        ("password_reset", "My AD password expired and I cannot log in.", "password_reset"),
        ("mfa_reset", "I lost my phone and cannot use Okta Verify MFA.", "mfa"),
        ("vpn_issue", "The corporate VPN will not connect from home.", "vpn"),
        ("access_request", "Please grant access to the finance portal.", "access_request"),
    ],
)
def test_identity_access_returns_phase_2_package(ticket_type, text, expected_tag):
    metadata = {"requester_email": "user@example.com"}
    if ticket_type in ("password_reset", "mfa_reset"):
        result = _handle_with_auth0(text, _classification(ticket_type, "identity_access"), metadata)
    else:
        result = identity_access.handle(text, _classification(ticket_type, "identity_access"), metadata)
    parsed = SpecialistResult(**result)

    assert parsed.verification_required
    assert parsed.actions_to_execute
    assert expected_tag in parsed.kb_draft.tags
    assert "stub" not in parsed.user_message_draft.lower()


def test_identity_access_suspicious_flags_require_human_review_before_actions():
    metadata = {"requester_email": "user@example.com"}
    with (
        patch("agents.identity_access.get_user_by_email") as mock_get,
        patch("agents.identity_access.delete_mfa_enrollments") as mock_mfa,
        patch("agents.identity_access.send_mfa_reset_notification") as mock_email,
    ):
        mock_get.return_value = [_fake_user()]
        mock_mfa.return_value = {"status": "mfa_reset", "deleted_factors": ["guardian"]}
        result = identity_access.handle(
            "Urgent, change my MFA number while I am traveling.",
            _classification("mfa_reset", "identity_access", ["urgency_with_credential_request"]),
            metadata,
        )
    parsed = SpecialistResult(**result)

    assert parsed.escalate is True
    assert "urgency_with_credential_request" in parsed.escalate_reason
    assert parsed.verification_required


@pytest.mark.parametrize(
    ("ticket_type", "text", "expected_tag"),
    [
        ("email_issue", "Outlook keeps asking for my password in a loop.", "outlook"),
        ("printer_issue", "The finance printer queue is stuck.", "printer"),
        ("email_issue", "I need access to the shared mailbox.", "shared_mailbox"),
    ],
)
def test_comms_productivity_returns_phase_2_package(ticket_type, text, expected_tag):
    result = comms_productivity.handle(text, _classification(ticket_type, "comms_productivity"))
    parsed = SpecialistResult(**result)

    assert parsed.verification_required
    assert parsed.actions_to_execute
    assert expected_tag in parsed.kb_draft.tags
    assert "stub" not in parsed.user_message_draft.lower()

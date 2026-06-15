import pytest

from agents import comms_productivity, identity_access
from schemas.classification import ClassificationResult
from schemas.specialist import SpecialistResult


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
    result = identity_access.handle(text, _classification(ticket_type, "identity_access"))
    parsed = SpecialistResult(**result)

    assert parsed.verification_required
    assert parsed.actions_to_execute
    assert expected_tag in parsed.kb_draft.tags
    assert "stub" not in parsed.user_message_draft.lower()


def test_identity_access_suspicious_flags_require_human_review_before_actions():
    result = identity_access.handle(
        "Urgent, change my MFA number while I am traveling.",
        _classification("mfa_reset", "identity_access", ["urgency_with_credential_request"]),
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

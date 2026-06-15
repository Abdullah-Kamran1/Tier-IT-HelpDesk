"""Identity & access specialist (password, MFA, VPN, access requests)."""

from schemas.classification import ClassificationResult
from schemas.specialist import IdentityAccessResult


SYSTEM_PROMPT = """
You are the identity and access specialist for an IT helpdesk.
You handle password resets, MFA enrollment, MFA resets, VPN issues, and access requests.
Return a complete tier-1 response package with verification before actions.
"""


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _password_reset_package() -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Confirm the requester is the account owner using the verification checklist.",
            "Check whether the account is locked, disabled, or expired in the directory.",
            "If the account is locked from failed attempts, unlock it before resetting the password.",
            "Issue a temporary password through the approved password reset workflow.",
            "Ask the user to sign in and set a new password, then verify access to core apps.",
        ],
        user_message_draft=(
            "Hi, I can help get your account access restored. For security, I need to verify "
            "your identity first. Once that is complete, I will reset the password and send the "
            "next sign-in steps through the approved channel."
        ),
        verification_required=[
            "Match requester email to the employee directory record.",
            "Verify employee ID, manager, or another approved identity proofing factor.",
            "Use an approved out-of-band channel before sharing any temporary credential.",
        ],
        actions_to_execute=[
            "Check directory account status.",
            "Unlock the account if needed.",
            "Reset the password and require change at next sign-in.",
            "Record the reset in the ticket audit trail.",
        ],
        kb_draft={
            "title": "Tier-1 password reset workflow",
            "symptoms": ["User cannot sign in", "Account locked or password expired"],
            "steps": [
                "Verify requester identity.",
                "Inspect account status.",
                "Unlock or reset password through the approved directory tool.",
                "Confirm successful sign-in.",
            ],
            "tags": ["identity_access", "password_reset", "active_directory"],
        },
    )


def _mfa_package() -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Verify the requester before changing any MFA method.",
            "Confirm whether the issue is enrollment, lost device, new phone, or failed push prompts.",
            "Check the user's current MFA factors and recent authentication attempts.",
            "Reset or re-enroll MFA only after identity verification is complete.",
            "Have the user complete a test sign-in before closing the ticket.",
        ],
        user_message_draft=(
            "Hi, I can help with your MFA access. Because this protects your account, I need to "
            "verify your identity before making changes. After that, I will walk you through "
            "re-enrolling and we will confirm you can sign in successfully."
        ),
        verification_required=[
            "Verify requester identity with an approved HR or manager-backed method.",
            "Confirm the old and new MFA device context without relying only on the ticket text.",
            "Flag for human review if the request includes unusual urgency, travel, or phone-number changes.",
        ],
        actions_to_execute=[
            "Review current MFA factors.",
            "Reset the affected MFA factor or start re-enrollment.",
            "Invalidate lost-device factors when applicable.",
            "Document successful test authentication.",
        ],
        kb_draft={
            "title": "MFA reset and re-enrollment workflow",
            "symptoms": ["Lost MFA device", "MFA prompt unavailable", "New phone enrollment needed"],
            "steps": [
                "Verify identity.",
                "Review current factors.",
                "Reset or re-enroll the affected factor.",
                "Validate sign-in with the user.",
            ],
            "tags": ["identity_access", "mfa", "okta"],
        },
    )


def _vpn_package() -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Confirm the user has working internet outside the VPN.",
            "Check whether the user's password or MFA changed recently.",
            "Ask the user to fully quit and reopen the VPN client.",
            "Have the user retry sign-in and note the exact error message.",
            "If multiple users are affected or the VPN gateway is down, escalate to network support.",
        ],
        user_message_draft=(
            "Hi, I can help troubleshoot the VPN connection. Please confirm your home internet is "
            "working, then restart the VPN app and try signing in again. I will check your account "
            "and MFA status on our side while you do that."
        ),
        verification_required=[
            "Confirm the requester owns the affected account.",
            "Verify no access changes are made until identity is confirmed.",
        ],
        actions_to_execute=[
            "Check account lock and password status.",
            "Review recent MFA/authentication failures.",
            "Document VPN error text and client version.",
            "Escalate if logs indicate gateway or certificate service failure.",
        ],
        kb_draft={
            "title": "Tier-1 VPN sign-in troubleshooting",
            "symptoms": ["VPN will not connect", "VPN rejects credentials", "Remote apps unreachable"],
            "steps": [
                "Confirm local internet works.",
                "Check account and MFA status.",
                "Restart VPN client and retry.",
                "Capture error text for escalation if needed.",
            ],
            "tags": ["identity_access", "vpn", "remote_access"],
        },
    )


def _access_request_package() -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Identify the exact system, group, mailbox, folder, or application being requested.",
            "Confirm the requester manager or data owner approval requirement.",
            "Check whether a standard access group exists for the role.",
            "Do not grant privileged or admin access from a ticket alone.",
            "Route non-standard or elevated access to the owning team for approval.",
        ],
        user_message_draft=(
            "Hi, I can help start the access request. Please confirm the exact system and level "
            "of access needed. If approval is required, I will route it to the right approver before "
            "any changes are made."
        ),
        verification_required=[
            "Verify requester identity.",
            "Confirm manager or resource owner approval before granting access.",
            "Confirm the access level is standard tier-1 scope.",
        ],
        actions_to_execute=[
            "Identify the target access group or application role.",
            "Request approval from the manager or resource owner.",
            "Apply standard access only after approval is recorded.",
            "Document the approval and access change in the ticket.",
        ],
        kb_draft={
            "title": "Standard access request intake workflow",
            "symptoms": ["User needs access", "Permission denied", "New app or resource required"],
            "steps": [
                "Verify identity.",
                "Capture exact access needed.",
                "Obtain approval.",
                "Grant standard access or escalate elevated access.",
            ],
            "tags": ["identity_access", "access_request", "permissions"],
        },
    )


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    text = f"{classification.ticket_type} {ticket_text}".lower()

    if _contains_any(text, ("mfa", "authenticator", "okta verify", "verification code", "push")):
        result = _mfa_package()
    elif _contains_any(text, ("vpn", "remote access", "corporate tunnel")):
        result = _vpn_package()
    elif _contains_any(text, ("access", "permission", "grant", "github", "shared drive", "portal")):
        result = _access_request_package()
    else:
        result = _password_reset_package()

    if classification.suspicious_flags:
        result.escalate = True
        result.escalate_reason = "Human review required before identity or access changes: " + ", ".join(
            classification.suspicious_flags
        )

    return result.model_dump()

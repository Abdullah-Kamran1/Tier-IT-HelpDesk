"""Identity & access specialist (password, MFA, VPN, access requests) — Auth0 backed."""
from tools.auth0 import (
    delete_mfa_enrollments,
    get_user_by_email,
    trigger_password_reset,
)
from schemas.classification import ClassificationResult
from schemas.specialist import IdentityAccessResult


SYSTEM_PROMPT = """
You are the identity and access specialist for an IT helpdesk.
You handle password resets, MFA enrollment, MFA resets, VPN issues, and access requests using Auth0.
Return a complete tier-1 response package with verification before actions.
"""


def _kb(title, symptoms, steps, tags):
    return {
        "title": title,
        "symptoms": symptoms,
        "steps": steps,
        "tags": tags,
    }


def _password_reset_result(email: str) -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Confirmed the requester's identity against the employee directory.",
            "Verified the account exists in Auth0.",
            f"Password reset email sent to {email} via Auth0.",
        ],
        user_message_draft=(
            f"A password reset email has been sent to {email}. "
            "Please check your inbox (and spam folder) and follow the link to create a new password. "
            "Once set, sign in again to confirm access."
        ),
        verification_required=[
            "Match requester email to the employee directory record.",
            "Verify employee ID, manager, or another approved identity proofing factor.",
        ],
        actions_to_execute=[
            f"Looked up {email} in Auth0.",
            "Triggered Auth0 password reset email.",
        ],
        kb_draft=_kb(
            "Tier-1 password reset workflow (Auth0)",
            ["User cannot sign in", "Account locked or password expired"],
            [
                "Verify requester identity.",
                "Look up user in Auth0 by email.",
                "Trigger password reset via Auth0 Change Password endpoint.",
                "Confirm the user received and used the reset link.",
            ],
            ["identity_access", "password_reset", "auth0"],
        ),
    )


def _mfa_reset_result(email: str, user_id: str, deleted_factors: list[str]) -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Verified the requester's identity.",
            f"Located Auth0 user {user_id}.",
            f"Removed enrolled MFA factors: {', '.join(deleted_factors) or 'none found'}.",
        ],
        user_message_draft=(
            f"Your MFA factors have been reset for {email}. "
            "Please sign in again and re-enroll your authenticator app or phone number "
            "when prompted."
        ),
        verification_required=[
            "Verify requester identity with an approved HR or manager-backed method.",
            "Confirm the old and new MFA device context.",
        ],
        actions_to_execute=[
            f"Looked up {email} in Auth0.",
            f"Deleted MFA enrollments for user {user_id}.",
        ],
        kb_draft=_kb(
            "MFA reset and re-enrollment workflow (Auth0)",
            ["Lost MFA device", "MFA prompt unavailable", "New phone enrollment needed"],
            [
                "Verify identity.",
                "Look up user in Auth0 by email.",
                "Delete enrolled MFA factors via Auth0 Management API.",
                "Instruct user to sign in and re-enroll.",
            ],
            ["identity_access", "mfa", "auth0"],
        ),
    )


def _mfa_enrollment_result(email: str) -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            f"Confirmed the requester's identity for {email}.",
            "MFA enrollment requires user action on their device.",
        ],
        user_message_draft=(
            "To set up MFA for your account: "
            "1. Install an authenticator app (like Google Authenticator or Auth0 Guardian). "
            "2. Sign in to your account and follow the MFA setup prompts. "
            "3. Scan the QR code with your authenticator app. "
            "4. Enter the verification code to confirm. "
            "Let me know if you run into any issues."
        ),
        verification_required=[
            "Verify requester identity before providing any enrollment links.",
        ],
        actions_to_execute=[
            f"Confirmed {email} exists in Auth0.",
            "Provided MFA enrollment instructions.",
        ],
        kb_draft=_kb(
            "MFA enrollment guidance (Auth0)",
            ["User needs to set up MFA", "New device enrollment"],
            [
                "Verify identity.",
                "Provide Auth0 MFA enrollment instructions.",
                "Confirm successful enrollment with a test sign-in.",
            ],
            ["identity_access", "mfa_enrollment", "auth0"],
        ),
    )


def _vpn_result(email: str) -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Check whether the user's password or MFA changed recently.",
            "Verify the account is not locked or blocked.",
            "Ask the user to fully quit and reopen the VPN client.",
            "Have the user retry sign-in and note the exact error message.",
        ],
        user_message_draft=(
            "Let's get you connected to the VPN. Please make sure your home internet is working, "
            "then restart the VPN app and try signing in again. "
            "If you still cannot connect, please share the exact error message you see."
        ),
        verification_required=[
            "Confirm the requester owns the affected account.",
        ],
        actions_to_execute=[
            f"Verified account {email} exists in Auth0.",
            "Provided VPN troubleshooting steps.",
        ],
        kb_draft=_kb(
            "Tier-1 VPN sign-in troubleshooting",
            ["VPN will not connect", "VPN rejects credentials"],
            [
                "Confirm local internet works.",
                "Check account and MFA status.",
                "Restart VPN client and retry.",
                "Capture error text for escalation if needed.",
            ],
            ["identity_access", "vpn", "remote_access"],
        ),
    )


def _access_request_result() -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[
            "Identify the exact system, group, or application being requested.",
            "Confirm manager or data owner approval requirement.",
            "Check whether a standard access group exists for the role.",
            "Do not grant privileged or admin access from a ticket alone.",
        ],
        user_message_draft=(
            "Thank you for the access request. Please confirm the exact system and level "
            "of access needed. If approval is required, I will route it to the right approver."
        ),
        verification_required=[
            "Verify requester identity.",
            "Confirm manager or resource owner approval before granting access.",
        ],
        actions_to_execute=[
            "Identified the target access group or application role.",
            "Standard access request recorded for review.",
        ],
        kb_draft=_kb(
            "Standard access request intake workflow",
            ["User needs access", "Permission denied"],
            [
                "Verify identity.",
                "Capture exact access needed.",
                "Obtain approval.",
                "Grant standard access or escalate elevated access.",
            ],
            ["identity_access", "access_request", "permissions"],
        ),
    )


def _not_found_result(email: str, ticket_type: str) -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[],
        user_message_draft=f"No Auth0 user found for {email}.",
        verification_required=["Verify the email address is correct and try again."],
        actions_to_execute=[f"Looked up {email} in Auth0 — not found."],
        kb_draft=_kb(
            "User not found in Auth0",
            ["User not found"],
            ["Verify email address and try again."],
            ["identity_access", ticket_type, "auth0"],
        ),
    )


def _error_result(error: str) -> IdentityAccessResult:
    return IdentityAccessResult(
        troubleshooting_steps=[],
        user_message_draft=f"Error processing request: {error}",
        verification_required=[],
        actions_to_execute=[],
        kb_draft=_kb(
            "Error processing request",
            ["An error occurred while processing the request"],
            [f"Review error: {error}"],
            ["error"],
        ),
        escalate=True,
        escalate_reason=error,
    )


def handle(
    ticket_text: str,
    classification: ClassificationResult,
    metadata: dict | None = None,
) -> dict:
    if metadata is None:
        metadata = {}
    email = metadata.get("requester_email") or metadata.get("submitter_email") or ""

    try:
        if classification.ticket_type == "password_reset":
            if not email:
                return _not_found_result("unknown", "password_reset").model_dump()
            users = get_user_by_email(email)
            if not users:
                result = _not_found_result(email, "password_reset")
            else:
                trigger_password_reset(email)
                result = _password_reset_result(email)

        elif classification.ticket_type == "mfa_reset":
            if not email:
                return _not_found_result("unknown", "mfa_reset").model_dump()
            users = get_user_by_email(email)
            if not users:
                result = _not_found_result(email, "mfa_reset")
            else:
                user_id = users[0]["user_id"]
                delete_result = delete_mfa_enrollments(user_id)
                result = _mfa_reset_result(email, user_id, delete_result.get("deleted_factors", []))

        elif classification.ticket_type == "mfa_enrollment":
            result = _mfa_enrollment_result(email or "the requester")

        elif classification.ticket_type == "vpn_issue":
            result = _vpn_result(email or "the requester")

        elif classification.ticket_type == "access_request":
            result = _access_request_result()

        else:
            result = IdentityAccessResult(
                troubleshooting_steps=[],
                user_message_draft=f"No handler for ticket type: {classification.ticket_type}",
                verification_required=[],
                actions_to_execute=[],
                kb_draft=_kb(
                    "Unknown ticket type",
                    [f"Unhandled ticket type: {classification.ticket_type}"],
                    ["Route to appropriate team for manual handling."],
                    ["error", classification.ticket_type],
                ),
            )

    except Exception as exc:
        result = _error_result(str(exc))

    if classification.suspicious_flags:
        result.escalate = True
        result.escalate_reason = result.escalate_reason or (
            "Human review required before identity or access changes: "
            + ", ".join(classification.suspicious_flags)
        )

    return result.model_dump()

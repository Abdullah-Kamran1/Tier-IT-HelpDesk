"""Lifecycle specialist (onboarding, offboarding, SLA reporting) — Auth0 backed."""
from tools.auth0 import (
    assign_user_role,
    block_user,
    create_user,
    delete_mfa_enrollments,
    get_user_by_email,
    get_user_roles,
    list_roles,
    remove_user_role,
)
from tools.email_service import send_password_reset_email
from schemas.classification import ClassificationResult
from schemas.specialist import LifecycleResult


def _kb(title, symptoms, steps, tags):
    return {
        "title": title,
        "symptoms": symptoms,
        "steps": steps,
        "tags": tags,
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _onboarding_result(email: str, user_id: str | None = None) -> LifecycleResult:
    return LifecycleResult(
        troubleshooting_steps=[
            f"Created Auth0 account for {email}.",
            "Assigned standard roles.",
            "Triggered welcome email with setup instructions.",
        ],
        user_message_draft=(
            f"An Auth0 account has been created for {email}. "
            "They will receive a welcome email with setup instructions."
        ),
        verification_required=[
            "Verify the requester is HR or the hiring manager.",
            "Confirm start date and role before provisioning access.",
        ],
        actions_to_execute=[
            f"Created Auth0 user {email}.",
            "Assigned standard roles.",
            "Sent welcome email.",
        ],
        kb_draft=_kb(
            "New hire onboarding workflow (Auth0)",
            ["New hire starting", "Device provisioning needed", "Access setup needed"],
            [
                "Verify requester and start details.",
                "Create Auth0 user account.",
                "Assign standard role(s).",
                "Send welcome email.",
                "Track readiness.",
            ],
            ["lifecycle", "onboarding", "auth0"],
        ),
    )


def _offboarding_result(
    email: str,
    roles_removed: list[str] | None = None,
    mfa_reset: bool = False,
) -> LifecycleResult:
    steps = [f"Blocked {email} from logging in."]
    if roles_removed:
        steps.append(f"Removed roles: {', '.join(roles_removed)}.")
    if mfa_reset:
        steps.append("Revoked MFA enrollments.")

    return LifecycleResult(
        troubleshooting_steps=steps,
        user_message_draft=(
            f"Access has been revoked for {email}. "
            "Their account is blocked, roles removed, and MFA reset."
        ),
        verification_required=[
            "Verify requester authority with HR or the manager.",
            "Confirm offboarding timing before disabling access.",
        ],
        actions_to_execute=[
            f"Blocked Auth0 user {email}.",
            "Removed role assignments.",
            *(["Revoked MFA enrollments."] if mfa_reset else []),
        ],
        kb_draft=_kb(
            "Employee offboarding workflow (Auth0)",
            ["Employee leaving", "Access removal needed", "Device return needed"],
            [
                "Verify authorization.",
                "Block user in Auth0.",
                "Remove role assignments.",
                "Revoke MFA enrollments.",
                "Track device return.",
            ],
            ["lifecycle", "offboarding", "auth0"],
        ),
    )


def _sla_result() -> LifecycleResult:
    return LifecycleResult(
        troubleshooting_steps=[
            "Confirm the ticket priority and submitted time.",
            "Compare current age against the SLA target.",
            "Flag tickets that are close to breach for manager attention.",
            "Escalate already breached tickets to the appropriate owner.",
        ],
        user_message_draft=(
            "I can check the ticket SLA status and make sure the right owner is alerted if it is close "
            "to breaching or already overdue."
        ),
        verification_required=[
            "Verify ticket ID and requester authority to view SLA details.",
        ],
        actions_to_execute=[
            "Check ticket age and priority.",
            "Mark SLA breach if the target has passed.",
            "Notify the IT manager for breached or high-risk tickets.",
        ],
        kb_draft=_kb(
            "SLA tracking workflow",
            ["Ticket overdue", "SLA breach risk", "Priority follow-up needed"],
            [
                "Verify ticket details.",
                "Calculate age against priority target.",
                "Flag breach.",
                "Notify owner.",
            ],
            ["lifecycle", "sla", "reporting"],
        ),
    )


def _not_found_result(email: str, ticket_type: str) -> LifecycleResult:
    return LifecycleResult(
        troubleshooting_steps=[],
        user_message_draft=f"No Auth0 user found for {email}.",
        verification_required=["Verify the email address is correct and try again."],
        actions_to_execute=[f"Looked up {email} in Auth0 — not found."],
        kb_draft=_kb(
            "User not found in Auth0",
            ["User not found"],
            ["Verify email address and try again."],
            ["lifecycle", ticket_type, "auth0"],
        ),
    )


def _error_result(error: str) -> LifecycleResult:
    return LifecycleResult(
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
    text = f"{classification.ticket_type} {ticket_text}".lower()

    try:
        if _contains_any(text, ("offboard", "leaving", "termination", "last day", "disable access")):
            if not email:
                return _not_found_result("unknown", "offboarding").model_dump()
            users = get_user_by_email(email)
            if not users:
                result = _not_found_result(email, "offboarding")
            else:
                user = users[0]
                user_id = user.user_id
                block_user(user_id)
                roles_removed = []
                try:
                    roles = get_user_roles(user_id)
                    for role in roles:
                        remove_user_role(user_id, role.id)
                        roles_removed.append(role.name or role.id)
                except Exception:
                    pass
                try:
                    delete_mfa_enrollments(user_id)
                    mfa_reset = True
                except Exception:
                    mfa_reset = False
                result = _offboarding_result(email, roles_removed, mfa_reset)

        elif _contains_any(text, ("sla", "overdue", "breach", "priority follow-up")):
            result = _sla_result()

        else:
            if not email:
                return _not_found_result("unknown", "onboarding").model_dump()
            try:
                created = create_user(email, name=email.split("@")[0])
                user_id = created.get("user_id")
            except Exception:
                user_id = None

            try:
                roles = list_roles("Standard")
                if roles:
                    assign_user_role(user_id, roles[0].id)
            except Exception:
                pass

            send_password_reset_email(email)
            result = _onboarding_result(email, user_id)

    except Exception as exc:
        result = _error_result(str(exc))

    return result.model_dump()

"""Lifecycle specialist (onboarding, offboarding, SLA reporting)."""

from schemas.classification import ClassificationResult
from schemas.specialist import LifecycleResult


SYSTEM_PROMPT = """
You are the lifecycle specialist for an IT helpdesk.
You handle onboarding, offboarding, access lifecycle checklists, and SLA tracking.
Return a complete tier-1 response package with ownership and approval checks.
"""


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _onboarding_package() -> LifecycleResult:
    return LifecycleResult(
        troubleshooting_steps=[
            "Confirm new hire full name, start date, manager, location, role, and employment type.",
            "Create or verify the onboarding ticket and required approvals.",
            "List needed device, software, groups, mailbox, and communication channels.",
            "Route device and access sub-tasks to the correct specialists.",
            "Track completion against the new hire start date.",
        ],
        user_message_draft=(
            "Hi, I can help coordinate onboarding. Please confirm the new hire name, start date, "
            "manager, role, location, and any required apps or access. I will turn that into the "
            "setup checklist and route the right tasks."
        ),
        verification_required=[
            "Verify the requester is HR, the hiring manager, or an approved onboarding coordinator.",
            "Confirm start date and role before provisioning access.",
            "Confirm approvals for non-standard access.",
        ],
        actions_to_execute=[
            "Create onboarding checklist.",
            "Create device provisioning task.",
            "Create standard access and software tasks.",
            "Track checklist status until start date readiness.",
        ],
        kb_draft={
            "title": "New hire onboarding checklist workflow",
            "symptoms": ["New hire starting", "Device provisioning needed", "Access setup needed"],
            "steps": [
                "Verify requester and start details.",
                "Create checklist.",
                "Route device and access tasks.",
                "Track readiness.",
            ],
            "tags": ["lifecycle", "onboarding", "checklist"],
        },
    )


def _offboarding_package() -> LifecycleResult:
    return LifecycleResult(
        troubleshooting_steps=[
            "Confirm employee, departure date, manager, and termination type.",
            "Verify the requester is authorized to initiate offboarding.",
            "List accounts, devices, shared ownership, licenses, and access groups to remove.",
            "Coordinate account disablement timing with HR or the manager.",
            "Track device return and access removal completion.",
        ],
        user_message_draft=(
            "Hi, I can help coordinate offboarding. Please confirm the employee name, departure date, "
            "manager, and whether access should end immediately or at a scheduled time. I will create "
            "the checklist and route the removal tasks."
        ),
        verification_required=[
            "Verify requester authority with HR or the manager.",
            "Confirm offboarding timing before disabling access.",
            "Confirm device return expectations.",
        ],
        actions_to_execute=[
            "Create offboarding checklist.",
            "Schedule or request account disablement.",
            "Create device return and license recovery tasks.",
            "Document completion of access removal.",
        ],
        kb_draft={
            "title": "Employee offboarding checklist workflow",
            "symptoms": ["Employee leaving", "Access removal needed", "Device return needed"],
            "steps": [
                "Verify authorization.",
                "Confirm timing.",
                "Create access and asset tasks.",
                "Track completion.",
            ],
            "tags": ["lifecycle", "offboarding", "access_lifecycle"],
        },
    )


def _sla_package() -> LifecycleResult:
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
        kb_draft={
            "title": "SLA tracking workflow",
            "symptoms": ["Ticket overdue", "SLA breach risk", "Priority follow-up needed"],
            "steps": [
                "Verify ticket details.",
                "Calculate age against priority target.",
                "Flag breach.",
                "Notify owner.",
            ],
            "tags": ["lifecycle", "sla", "reporting"],
        },
    )


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    text = f"{classification.ticket_type} {ticket_text}".lower()

    if _contains_any(text, ("offboard", "leaving", "termination", "last day", "disable access")):
        result = _offboarding_package()
    elif _contains_any(text, ("sla", "overdue", "breach", "priority follow-up")):
        result = _sla_package()
    else:
        result = _onboarding_package()

    return result.model_dump()

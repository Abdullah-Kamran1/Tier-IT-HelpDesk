"""Comms & productivity specialist (email, printer, calendar)."""

from schemas.classification import ClassificationResult
from schemas.specialist import CommsProductivityResult


SYSTEM_PROMPT = """
You are the communications and productivity specialist for an IT helpdesk.
You handle Outlook, email, calendars, printers, messaging tools, and shared mailboxes.
Return a complete tier-1 response package with safe, plain-language steps.
"""


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _printer_package() -> CommsProductivityResult:
    return CommsProductivityResult(
        troubleshooting_steps=[
            "Confirm whether one user or multiple users are affected.",
            "Ask the user to try a simple test page and note any printer-panel error.",
            "Check the print queue for stuck jobs and pause/resume the queue if needed.",
            "Restart the printer only if it is safe and no one is actively using it.",
            "Escalate hardware faults such as fuser, jam sensor, or repeated service codes.",
        ],
        user_message_draft=(
            "Hi, I can help with the printer issue. Please send the printer name or location and "
            "any error shown on the display. I will check the queue and try the standard reset steps."
        ),
        verification_required=[
            "Confirm the printer name or physical location.",
            "Confirm whether the requester is allowed to print to that queue.",
        ],
        actions_to_execute=[
            "Inspect print queue status.",
            "Clear stuck jobs when appropriate.",
            "Restart or pause/resume the queue.",
            "Capture hardware error code for escalation if it persists.",
        ],
        kb_draft={
            "title": "Printer queue and panel error troubleshooting",
            "symptoms": ["Print jobs stuck", "Printer displays an error", "Shared printer unavailable"],
            "steps": [
                "Identify printer and scope.",
                "Check queue.",
                "Clear stuck jobs.",
                "Escalate persistent hardware codes.",
            ],
            "tags": ["comms_productivity", "printer", "print_queue"],
        },
    )


def _shared_mailbox_package() -> CommsProductivityResult:
    return CommsProductivityResult(
        troubleshooting_steps=[
            "Confirm the shared mailbox name and the access level requested.",
            "Verify approval from the mailbox owner or manager.",
            "Check whether the user already has access and Outlook just needs a restart.",
            "Apply standard access only after approval is recorded.",
            "Ask the user to restart Outlook or webmail and confirm the mailbox appears.",
        ],
        user_message_draft=(
            "Hi, I can help with the shared mailbox. Please confirm the mailbox name and the "
            "access you need. If approval is required, I will request it before making changes."
        ),
        verification_required=[
            "Verify requester identity.",
            "Confirm approval from the mailbox owner or manager.",
            "Confirm the requested permission level is standard tier-1 scope.",
        ],
        actions_to_execute=[
            "Check current shared mailbox permissions.",
            "Request or confirm owner approval.",
            "Apply standard mailbox permission after approval.",
            "Ask the user to restart Outlook or test in webmail.",
        ],
        kb_draft={
            "title": "Shared mailbox access workflow",
            "symptoms": ["Shared mailbox missing", "Cannot open shared mailbox", "Mailbox access requested"],
            "steps": [
                "Verify requester and approval.",
                "Check existing permissions.",
                "Grant approved access.",
                "Validate in Outlook or webmail.",
            ],
            "tags": ["comms_productivity", "shared_mailbox", "outlook"],
        },
    )


def _outlook_package() -> CommsProductivityResult:
    return CommsProductivityResult(
        troubleshooting_steps=[
            "Confirm whether webmail works while the desktop app is failing.",
            "Check whether the user recently changed their password.",
            "Ask the user to restart Outlook and sign in again.",
            "If prompts loop, clear cached credentials using the approved desktop support procedure.",
            "Escalate if many users are affected or mail flow is delayed tenant-wide.",
        ],
        user_message_draft=(
            "Hi, I can help with Outlook. Please try signing in through webmail first so we can "
            "separate an account issue from a desktop app issue. I will guide you through the next "
            "steps based on what happens there."
        ),
        verification_required=[
            "Verify the requester owns the affected mailbox.",
            "Confirm no mailbox permission or credential changes are made without identity verification.",
        ],
        actions_to_execute=[
            "Check mailbox/account status.",
            "Compare webmail and desktop Outlook behavior.",
            "Clear cached credentials if the password prompt loops.",
            "Document any service-wide symptoms before escalation.",
        ],
        kb_draft={
            "title": "Outlook sign-in and send/receive troubleshooting",
            "symptoms": ["Outlook password prompts", "Email will not load", "Desktop app not syncing"],
            "steps": [
                "Test webmail.",
                "Restart Outlook.",
                "Check account status.",
                "Clear cached credentials if needed.",
            ],
            "tags": ["comms_productivity", "outlook", "email"],
        },
    )


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    text = f"{classification.ticket_type} {ticket_text}".lower()

    if _contains_any(text, ("printer", "print", "queue", "fuser")):
        result = _printer_package()
    elif _contains_any(text, ("shared mailbox", "mailbox access", "distribution list")):
        result = _shared_mailbox_package()
    else:
        result = _outlook_package()

    return result.model_dump()

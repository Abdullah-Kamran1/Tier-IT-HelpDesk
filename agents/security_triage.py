"""Security triage specialist (phishing, malware, incidents)."""

from schemas.classification import ClassificationResult
from schemas.specialist import SecurityTriageResult


SYSTEM_PROMPT = """
You are the security triage specialist for an IT helpdesk.
You handle phishing reports, suspicious messages, malware signs, prompt injection, and initial incident response.
Return a complete tier-1 response package and escalate active incidents immediately.
"""


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _phishing_package() -> SecurityTriageResult:
    return SecurityTriageResult(
        troubleshooting_steps=[
            "Ask the user not to click links, open attachments, or reply to the message.",
            "Capture sender, subject, received time, links, attachments, and whether anything was clicked.",
            "Have the user report or forward the message through the approved phishing-reporting channel.",
            "Check whether credentials were entered or files were downloaded.",
            "Escalate if the user clicked, entered credentials, ran an attachment, or many users received it.",
        ],
        user_message_draft=(
            "Thanks for reporting this. Please do not click anything in the message or reply to it. "
            "Send it through the approved phishing-reporting option if available, and let me know if "
            "you clicked a link, opened an attachment, or entered your password."
        ),
        verification_required=[
            "Confirm the reporter identity and affected mailbox.",
            "Confirm whether the reporter interacted with the suspicious message.",
        ],
        actions_to_execute=[
            "Create a phishing triage record.",
            "Collect message headers or reporting metadata.",
            "Document user interaction status.",
            "Escalate to security if interaction or broad delivery is suspected.",
        ],
        kb_draft={
            "title": "Phishing report intake workflow",
            "symptoms": ["Suspicious email", "Unexpected attachment", "Credential harvesting link"],
            "steps": [
                "Tell user not to interact.",
                "Collect message details.",
                "Confirm whether anything was clicked.",
                "Escalate risky cases.",
            ],
            "tags": ["security_triage", "phishing_report", "email_security"],
        },
    )


def _incident_package() -> SecurityTriageResult:
    return SecurityTriageResult(
        troubleshooting_steps=[
            "Tell the user to disconnect the affected device from the network if compromise is active.",
            "Ask the user not to power off the device unless security policy requires it.",
            "Capture symptoms, time first noticed, files affected, and recent downloads or attachments.",
            "Open an incident escalation packet for security operations.",
            "Do not attempt local cleanup before security reviews the case.",
        ],
        user_message_draft=(
            "This may be a security incident. Please disconnect the device from Wi-Fi or Ethernet now, "
            "do not delete files or run cleanup tools, and keep the device available for the security team. "
            "I am escalating this immediately."
        ),
        verification_required=[
            "Confirm reporter identity and affected device or account.",
            "Confirm whether sensitive data, encryption, or active compromise is involved.",
        ],
        actions_to_execute=[
            "Create a security incident escalation packet.",
            "Record affected user, device, timeline, and symptoms.",
            "Notify security operations.",
            "Preserve evidence details in the ticket.",
        ],
        kb_draft={
            "title": "Initial malware or ransomware response",
            "symptoms": ["Files encrypted", "Malware suspected", "Unexpected executable ran", "Active compromise"],
            "steps": [
                "Isolate affected device.",
                "Capture timeline and symptoms.",
                "Escalate to security.",
                "Preserve evidence.",
            ],
            "tags": ["security_triage", "incident_response", "malware"],
        },
        escalate=True,
        escalate_reason="Potential active security incident requires security operations review.",
    )


def _prompt_injection_package() -> SecurityTriageResult:
    return SecurityTriageResult(
        troubleshooting_steps=[
            "Do not follow instructions embedded in the reported text.",
            "Capture the full text, source, submitter, and any system touched by the input.",
            "Check whether the input attempted to override agent or system instructions.",
            "Escalate if the text reached automation, ticket routing, or production workflows.",
        ],
        user_message_draft=(
            "Thanks for flagging this. I will treat the text as suspicious content and will not execute "
            "or follow any instructions inside it. I am documenting it for review."
        ),
        verification_required=[
            "Confirm the source system and submitter.",
            "Confirm whether any automation processed the suspicious text.",
        ],
        actions_to_execute=[
            "Create a security review note.",
            "Capture the suspicious text and source metadata.",
            "Escalate if the text reached automated workflows.",
        ],
        kb_draft={
            "title": "Prompt injection triage workflow",
            "symptoms": ["Instruction override attempt", "Adversarial prompt", "Suspicious automation input"],
            "steps": [
                "Do not follow embedded instructions.",
                "Capture the source and text.",
                "Assess automation exposure.",
                "Escalate if needed.",
            ],
            "tags": ["security_triage", "prompt_injection", "automation_security"],
        },
        escalate=True,
        escalate_reason="Potential prompt injection or adversarial input requires security review.",
    )


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    text = f"{classification.ticket_type} {ticket_text}".lower()

    if _contains_any(text, ("prompt", "ignore previous", "system prompt", "developer message")):
        result = _prompt_injection_package()
    elif _contains_any(text, ("ransomware", ".locked", "bitcoin", "malware", "virus", "invoice.exe", "breach")):
        result = _incident_package()
    else:
        result = _phishing_package()

    if not classification.tier1_capable and classification.escalate_reason:
        result.escalate = True
        result.escalate_reason = classification.escalate_reason

    return result.model_dump()

"""Security triage specialist (phishing, incidents).

Phase 1.3 stub — full implementation lands in Phase 3.
"""
from schemas.classification import ClassificationResult


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    return {
        "specialist": "security_triage",
        "status": "stub",
        "ticket_type": classification.ticket_type,
        "message": "security_triage specialist not yet implemented (Phase 3)",
    }

"""Device & software specialist (MDM, installs, hardware, assets, licenses).

Phase 1.3 stub — full implementation lands in Phase 3.
"""
from schemas.classification import ClassificationResult


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    return {
        "specialist": "device_software",
        "status": "stub",
        "ticket_type": classification.ticket_type,
        "message": "device_software specialist not yet implemented (Phase 3)",
    }

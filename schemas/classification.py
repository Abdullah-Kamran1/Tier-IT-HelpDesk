from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel


class ClassificationResult(BaseModel):
    ticket_type: str
    priority: str
    tier1_capable: bool
    route_to: str
    confidence: float
    suspicious_flags: list[str] = []
    duplicate_signal: bool = False
    split_routes: Optional[list[str]] = None
    escalate_reason: Optional[str] = None
    classification_notes: str = ""
    sla_hours: Optional[float] = None
    source_id: Optional[str] = None

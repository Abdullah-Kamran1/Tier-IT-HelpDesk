from typing import Optional

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, model_validator


class KBDraft(BaseModel):
    title: str
    symptoms: list[str]
    steps: list[str]
    tags: list[str]


class SpecialistResult(BaseModel):
    troubleshooting_steps: list[str]
    user_message_draft: str
    verification_required: list[str]
    actions_to_execute: list[str]
    kb_draft: KBDraft
    escalate: bool = False
    escalate_reason: Optional[str] = None

    @model_validator(mode="after")
    def require_verification_before_actions(self):
        if self.actions_to_execute and not self.verification_required:
            raise ValueError("verification_required must be listed before any actions_to_execute")
        if self.escalate and not self.escalate_reason:
            raise ValueError("escalate_reason is required when escalate is true")
        return self


IdentityAccessResult = SpecialistResult
CommsProductivityResult = SpecialistResult
DeviceSoftwareResult = SpecialistResult
SecurityTriageResult = SpecialistResult
LifecycleResult = SpecialistResult

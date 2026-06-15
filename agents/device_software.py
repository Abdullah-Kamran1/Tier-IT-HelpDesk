"""Device & software specialist (MDM, installs, hardware, assets, licenses)."""

from schemas.classification import ClassificationResult
from schemas.specialist import DeviceSoftwareResult


SYSTEM_PROMPT = """
You are the device and software specialist for an IT helpdesk.
You handle MDM enrollment, software installs, license requests, hardware issues, and asset updates.
Return a complete tier-1 response package with safe, plain-language steps.
"""


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _mdm_package() -> DeviceSoftwareResult:
    return DeviceSoftwareResult(
        troubleshooting_steps=[
            "Confirm the device serial number, platform, and assigned user.",
            "Check whether the device is already present in MDM.",
            "Ask the user to connect to a stable network and start the enrollment flow.",
            "Confirm required profiles and compliance checks finish successfully.",
            "Escalate if enrollment fails with a server-side MDM or certificate error.",
        ],
        user_message_draft=(
            "Hi, I can help with device enrollment. Please send the device serial number and confirm "
            "whether it is a company device. I will check the management record and guide you through "
            "the enrollment steps."
        ),
        verification_required=[
            "Verify the requester is assigned to the device or is an approved onboarding contact.",
            "Confirm the device is company-owned or approved for enrollment.",
        ],
        actions_to_execute=[
            "Look up the asset record.",
            "Check MDM enrollment status.",
            "Trigger or document the enrollment workflow.",
            "Confirm compliance status after enrollment.",
        ],
        kb_draft={
            "title": "MDM enrollment workflow",
            "symptoms": ["Device not managed", "Enrollment failed", "Compliance profile missing"],
            "steps": [
                "Verify user and device assignment.",
                "Check the asset record.",
                "Run enrollment.",
                "Confirm compliance.",
            ],
            "tags": ["device_software", "mdm_enrollment", "asset"],
        },
    )


def _software_package() -> DeviceSoftwareResult:
    return DeviceSoftwareResult(
        troubleshooting_steps=[
            "Confirm the application name, device, operating system, and business reason.",
            "Check whether the software is approved and already licensed.",
            "Confirm whether the user can install from the company portal.",
            "Assign or request the license if needed.",
            "Escalate non-standard, admin-only, or security-sensitive software requests.",
        ],
        user_message_draft=(
            "Hi, I can help with the software request. Please confirm the app name, the device you "
            "need it on, and the business reason. I will check approval and licensing before assigning it."
        ),
        verification_required=[
            "Verify requester identity and device assignment.",
            "Confirm manager or application owner approval if the software is restricted.",
            "Confirm license availability before assigning paid software.",
        ],
        actions_to_execute=[
            "Check approved software catalog.",
            "Check license availability.",
            "Assign software through the company portal or MDM.",
            "Document assignment and installation confirmation.",
        ],
        kb_draft={
            "title": "Standard software install request workflow",
            "symptoms": ["Software needed", "Application missing", "License requested"],
            "steps": [
                "Capture app and device details.",
                "Validate approval and license.",
                "Assign software.",
                "Confirm installation.",
            ],
            "tags": ["device_software", "software_install", "license"],
        },
    )


def _hardware_package() -> DeviceSoftwareResult:
    return DeviceSoftwareResult(
        troubleshooting_steps=[
            "Confirm the device type, asset tag, and exact physical symptom.",
            "Ask the user to stop using the device if there is a safety risk.",
            "Capture photos or error messages when helpful.",
            "Check warranty and replacement eligibility.",
            "Escalate battery swelling, liquid damage, or repeated boot failure for hands-on support.",
        ],
        user_message_draft=(
            "Hi, I can help with the hardware issue. Please send the asset tag and a short description "
            "of what changed. If the device is hot, swollen, sparking, or physically unsafe, please stop "
            "using it and disconnect power."
        ),
        verification_required=[
            "Verify the requester is assigned to the device.",
            "Confirm the asset tag or serial number before updating records.",
        ],
        actions_to_execute=[
            "Look up asset and warranty status.",
            "Record the reported hardware symptom.",
            "Create a repair or replacement task if needed.",
            "Update asset notes with the current condition.",
        ],
        kb_draft={
            "title": "Hardware issue intake workflow",
            "symptoms": ["Device damaged", "Battery swelling", "Boot failure", "Peripheral failure"],
            "steps": [
                "Verify asset ownership.",
                "Assess safety risk.",
                "Capture symptom details.",
                "Create repair or replacement task.",
            ],
            "tags": ["device_software", "hardware_issue", "asset"],
        },
    )


def _asset_package() -> DeviceSoftwareResult:
    return DeviceSoftwareResult(
        troubleshooting_steps=[
            "Identify the asset tag, current user, requested owner, and location.",
            "Confirm the asset change is authorized.",
            "Check whether the device has open repair, lost, or offboarding status.",
            "Update the asset record only after verification.",
            "Add a ticket note describing the source of the change.",
        ],
        user_message_draft=(
            "Hi, I can help update the asset record. Please send the asset tag, current owner or "
            "location, and what needs to change. I will verify the details before updating the record."
        ),
        verification_required=[
            "Verify requester authority to change the asset record.",
            "Confirm asset tag or serial number.",
        ],
        actions_to_execute=[
            "Look up the asset record.",
            "Validate current ownership and status.",
            "Update owner, location, or notes.",
            "Record the change in the ticket.",
        ],
        kb_draft={
            "title": "Asset record update workflow",
            "symptoms": ["Asset owner incorrect", "Location incorrect", "Inventory update requested"],
            "steps": [
                "Verify request authority.",
                "Look up the asset.",
                "Update the record.",
                "Document the change.",
            ],
            "tags": ["device_software", "asset_update", "inventory"],
        },
    )


def handle(ticket_text: str, classification: ClassificationResult) -> dict:
    text = f"{classification.ticket_type} {ticket_text}".lower()

    if _contains_any(text, ("mdm", "enroll", "intune", "jamf", "management profile")):
        result = _mdm_package()
    elif _contains_any(text, ("hardware", "battery", "screen", "keyboard", "broken", "shattered", "laptop")):
        result = _hardware_package()
    elif _contains_any(text, ("asset", "serial", "inventory", "owner", "location")):
        result = _asset_package()
    else:
        result = _software_package()

    return result.model_dump()

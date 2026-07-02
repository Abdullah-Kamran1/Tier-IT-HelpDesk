"""General stub tool-call registry.

Phase 3 keeps these calls fake and deterministic. Phase 5 can replace the
underlying functions with real API integrations without changing call sites.
"""

from tools import auth0, email_service, itsm, messaging


TOOL_REGISTRY = {
    "auth0.get_user_by_email": auth0.get_user_by_email,
    "auth0.trigger_password_reset": auth0.trigger_password_reset,
    "auth0.block_user": auth0.block_user,
    "auth0.delete_mfa_enrollments": auth0.delete_mfa_enrollments,
    "auth0.create_mfa_enrollment_ticket": auth0.create_mfa_enrollment_ticket,
    "auth0.get_user_roles": auth0.get_user_roles,
    "auth0.assign_user_role": auth0.assign_user_role,
    "auth0.remove_user_role": auth0.remove_user_role,
    "auth0.list_roles": auth0.list_roles,
    "auth0.create_user": auth0.create_user,
    "itsm.create_ticket": itsm.create_ticket,
    "itsm.add_comment": itsm.add_comment,
    "itsm.update_status": itsm.update_status,
    "itsm.assign_ticket": itsm.assign_ticket,
    "itsm.get_asset": itsm.get_asset,
    "itsm.update_asset": itsm.update_asset,
    "itsm.create_kb_draft": itsm.create_kb_draft,
    "messaging.send_user_message": messaging.send_user_message,
    "messaging.notify_manager": messaging.notify_manager,
    "messaging.notify_channel": messaging.notify_channel,
    "email.send_helpdesk_email": email_service.send_helpdesk_email,
    "email.send_mfa_enrollment_email": email_service.send_mfa_enrollment_email,
    "email.send_password_reset_email": email_service.send_password_reset_email,
    "email.send_mfa_reset_notification": email_service.send_mfa_reset_notification,
}


def call_tool(name: str, **kwargs) -> dict:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return {
            "tool": name,
            "ok": False,
            "error": f"unknown tool '{name}'",
            "source": "stub",
        }

    return {
        "tool": name,
        "ok": True,
        "result": tool(**kwargs),
        "source": "stub",
    }

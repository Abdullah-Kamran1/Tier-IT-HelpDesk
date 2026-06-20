"""Auth0 Management API tools for identity & access operations using the official SDK."""
import os
from auth0.management import ManagementClient

# Load environment configuration variables
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_CONNECTION = os.getenv("AUTH0_CONNECTION", "Username-Password-Authentication")


class Auth0ToolKit:
    def __init__(self):
        """
        Initializes the Management API wrapper.
        By passing client_id and client_secret directly with token=None,
        the SDK handles the OAuth2 Machine-to-Machine token generation,
        caching, and auto-refresh mechanisms automatically.
        """

        self.auth0 = ManagementClient(
            domain=AUTH0_DOMAIN,
            client_id=AUTH0_CLIENT_ID,
            client_secret=AUTH0_CLIENT_SECRET
        )

    def get_user_by_email(self, email: str) -> list:
        """Finds user records corresponding to an email address."""
        try:
            # SDK maps directly to: GET /api/v2/users-by-email
            users = self.auth0.users.list_users_by_email(email=email)
            return users
        except Exception as e:
            raise RuntimeError(f"[AUTH0] get_user_by_email failed: {e}") from e

    def trigger_password_reset(self, email: str) -> dict:
        """Sends an Auth0 change password verification email."""
        try:
            self.auth0.tickets.change_password(
                email=email,
                client_id=AUTH0_CLIENT_ID,
            )
            return {"status": "reset_sent", "email": email}
        except Exception as e:
            raise RuntimeError(f"[AUTH0] trigger_password_reset failed: {e}") from e

    def block_user(self, user_id: str) -> dict:
        """Administratively blocks a user from logging in."""
        try:
            # SDK maps directly to: PATCH /api/v2/users/{id}
            self.auth0.users.update(user_id, {"blocked": True})
            return {"status": "blocked", "user_id": user_id}
        except Exception as e:
            raise RuntimeError(f"[AUTH0] block_user failed: {e}") from e

    def unlock_user(self, user_id: str) -> dict:
        """Administratively unblocks a user account profile."""
        try:
            # Reverses block states by setting blocked flag to False
            self.auth0.users.update(user_id, {"blocked": False})
            return {"status": "unlocked", "user_id": user_id}
        except Exception as e:
            raise RuntimeError(f"[AUTH0] unlock_user failed: {e}") from e

    def delete_mfa_enrollments(self, user_id: str) -> dict:
        """
        Queries active multi-factor enrollments and deletes them efficiently
        without guessing factor names or running loops unnecessarily.
        """
        deleted = []
        errors = []
        
        try:
            # 1. Ask Auth0 exactly what active MFA devices this specific user owns
            enrollments = self.auth0.users.get_enrollments(user_id)
            
            if not enrollments:
                return {"status": "mfa_reset", "user_id": user_id, "deleted_factors": [], "message": "No factors active."}

            # 2. Delete ONLY the factors that are actually registered
            for device in enrollments:
                device_id = device.get("id")
                device_type = device.get("type", "unknown")
                try:
                    self.auth0.guardian.enrollments.delete(device_id)
                    deleted.append(device_type)
                except Exception as inner_err:
                    errors.append({"factor": device_type, "error": f"[AUTH0] {inner_err}"})

            result = {"status": "mfa_reset", "user_id": user_id, "deleted_factors": deleted}
            if errors:
                result["errors"] = errors
            return result

        except Exception as e:
            raise RuntimeError(f"[AUTH0] delete_mfa_enrollments failed: {e}") from e

    def create_mfa_enrollment_ticket(
        self,
        user_id: str,
        email: str | None = None,
        factor: str | None = None,
        send_mail: bool = False,
    ) -> dict:
        """
        Generates a guardian enrollment ticket so the user can set up MFA.
        Returns the ticket URL that the user must visit to complete enrollment.
        """
        try:
            kwargs = {"user_id": user_id, "send_mail": send_mail}
            if email:
                kwargs["email"] = email
            if factor:
                kwargs["factor"] = factor

            ticket = self.auth0.guardian.enrollments.create_ticket(**kwargs)
            return {
                "status": "enrollment_ticket_created",
                "user_id": user_id,
                "ticket_url": ticket.ticket_url,
                "ticket_id": ticket.ticket_id,
            }
        except Exception as e:
            raise RuntimeError(f"[AUTH0] create_mfa_enrollment_ticket failed: {e}") from e


_toolkit = None


def _get_toolkit() -> Auth0ToolKit:
    global _toolkit
    if _toolkit is None:
        _toolkit = Auth0ToolKit()
    return _toolkit


def get_user_by_email(email: str) -> list:
    return _get_toolkit().get_user_by_email(email)


def trigger_password_reset(email: str) -> dict:
    return _get_toolkit().trigger_password_reset(email)


def block_user(user_id: str) -> dict:
    return _get_toolkit().block_user(user_id)


def unlock_user(user_id: str) -> dict:
    return _get_toolkit().unlock_user(user_id)


def delete_mfa_enrollments(user_id: str) -> dict:
    return _get_toolkit().delete_mfa_enrollments(user_id)


def create_mfa_enrollment_ticket(
    user_id: str,
    email: str | None = None,
    factor: str | None = None,
    send_mail: bool = False,
) -> dict:
    return _get_toolkit().create_mfa_enrollment_ticket(
        user_id=user_id, email=email, factor=factor, send_mail=send_mail,
    )
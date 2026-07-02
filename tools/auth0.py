"""Auth0 Management API + Authentication API tools for identity & access operations."""
import os
from auth0.management import ManagementClient
from auth0.authentication import Database

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
        self.db = Database(
            domain=AUTH0_DOMAIN,
            client_id=AUTH0_CLIENT_ID,
            client_secret=AUTH0_CLIENT_SECRET,
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
        """Sends Autho's own password reset email via the Authentication API."""
        try:
            result = self.db.change_password(
                email=email,
                connection="Username-Password-Authentication"
            )
            return {"status": "reset_email_sent", "email": email, "response": result}
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
        Deletes all registered MFA authentication methods for a user.
        Forces the user to re-enroll MFA.
        """
        try:
            self.auth0.users.authentication_methods.delete_all(
                user_id
            )

            return {
                "status": "mfa_reset",
                "user_id": user_id,
                "message": "All active authentication factors successfully cleared."
            }

        except Exception as e:
            raise RuntimeError(
                f"[AUTH0] delete_mfa_enrollments failed: {e}"
            ) from e

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

            ticket = self.auth0.guardian_tickets.create(**kwargs)
            return {
                "status": "enrollment_ticket_created",
                "user_id": user_id,
                "ticket_url": ticket.ticket_url,
                "ticket_id": ticket.ticket_id,
            }
        except Exception as e:
            raise RuntimeError(f"[AUTH0] create_mfa_enrollment_ticket failed: {e}") from e

    def get_user_roles(self, user_id: str) -> list:
        """List all Auth0 roles assigned to a user."""
        try:
            pager = self.auth0.users.roles.list(id=user_id)
            return list(pager)
        except Exception as e:
            raise RuntimeError(f"[AUTH0] get_user_roles failed: {e}") from e

    def assign_user_role(self, user_id: str, role_id: str) -> dict:
        """Assign an Auth0 role to a user."""
        try:
            self.auth0.users.roles.assign(id=user_id, roles=[role_id])
            return {"status": "assigned", "user_id": user_id, "role_id": role_id}
        except Exception as e:
            raise RuntimeError(f"[AUTH0] assign_user_role failed: {e}") from e

    def remove_user_role(self, user_id: str, role_id: str) -> dict:
        """Remove an Auth0 role from a user."""
        try:
            self.auth0.users.roles.delete(id=user_id, roles=[role_id])
            return {"status": "removed", "user_id": user_id, "role_id": role_id}
        except Exception as e:
            raise RuntimeError(f"[AUTH0] remove_user_role failed: {e}") from e

    def list_roles(self, name_filter: str | None = None) -> list:
        """List Auth0 roles, optionally filtered by name."""
        try:
            kwargs = {}
            if name_filter:
                kwargs["name_filter"] = name_filter
            pager = self.auth0.roles.list(**kwargs)
            return list(pager)
        except Exception as e:
            raise RuntimeError(f"[AUTH0] list_roles failed: {e}") from e

    def create_user(self, email: str, name: str, **kwargs) -> dict:
        """Create a new Auth0 user account."""
        try:
            payload = {
                "email": email,
                "name": name,
                "connection": AUTH0_CONNECTION,
                **kwargs,
            }
            user = self.auth0.users.create(payload)
            return {
                "status": "created",
                "user_id": user.user_id,
                "email": user.email,
            }
        except Exception as e:
            raise RuntimeError(f"[AUTH0] create_user failed: {e}") from e


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


def get_user_roles(user_id: str) -> list:
    return _get_toolkit().get_user_roles(user_id)


def assign_user_role(user_id: str, role_id: str) -> dict:
    return _get_toolkit().assign_user_role(user_id, role_id)


def remove_user_role(user_id: str, role_id: str) -> dict:
    return _get_toolkit().remove_user_role(user_id, role_id)


def list_roles(name_filter: str | None = None) -> list:
    return _get_toolkit().list_roles(name_filter)


def create_user(email: str, name: str, **kwargs) -> dict:
    return _get_toolkit().create_user(email, name, **kwargs)
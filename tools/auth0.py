"""Auth0 Management API tools for identity & access operations."""
import os

import requests


AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")

_MGMT_TOKEN: str | None = None


def _get_management_token() -> str:
    global _MGMT_TOKEN
    if _MGMT_TOKEN:
        return _MGMT_TOKEN

    r = requests.post(
        f"https://{AUTH0_DOMAIN}/oauth/token",
        json={
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "audience": f"https://{AUTH0_DOMAIN}/api/v2/",
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    r.raise_for_status()
    _MGMT_TOKEN = r.json()["access_token"]
    return _MGMT_TOKEN


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_management_token()}",
        "Content-Type": "application/json",
    }


def get_user_by_email(email: str) -> list:
    r = requests.get(
        f"https://{AUTH0_DOMAIN}/api/v2/users-by-email",
        headers=_headers(),
        params={"email": email},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def trigger_password_reset(email: str) -> dict:
    r = requests.post(
        f"https://{AUTH0_DOMAIN}/dbconnections/change_password",
        json={
            "client_id": AUTH0_CLIENT_ID,
            "email": email,
            "connection": os.getenv("AUTH0_CONNECTION", "Username-Password-Authentication"),
        },
        timeout=10,
    )
    r.raise_for_status()
    return {"status": "reset_sent", "email": email}


def block_user(user_id: str) -> dict:
    r = requests.patch(
        f"https://{AUTH0_DOMAIN}/api/v2/users/{user_id}",
        headers=_headers(),
        json={"blocked": True},
        timeout=10,
    )
    r.raise_for_status()
    return {"status": "blocked", "user_id": user_id}


def delete_mfa_enrollments(user_id: str) -> dict:
    FACTORS = [
        "duo", "google-authenticator", "guardian", "sms",
        "email", "otp", "recovery-code", "push-notification",
    ]
    deleted = []
    errors = []
    for factor in FACTORS:
        r = requests.delete(
            f"https://{AUTH0_DOMAIN}/api/v2/users/{user_id}/multifactor/{factor}",
            headers=_headers(),
            timeout=10,
        )
        if r.status_code == 204:
            deleted.append(factor)
        elif r.status_code != 404:
            errors.append({"factor": factor, "error": r.text})
    result = {"status": "mfa_reset", "user_id": user_id, "deleted_factors": deleted}
    if errors:
        result["errors"] = errors
    return result

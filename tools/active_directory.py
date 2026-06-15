"""Stub Active Directory / Microsoft Graph tool functions."""


def get_user(email: str) -> dict:
    return {
        "email": email,
        "display_name": "Test User",
        "locked": False,
        "disabled": False,
        "last_login": "2026-06-10T09:30:00Z",
        "groups": ["Employees"],
        "source": "stub",
    }


def reset_password(email: str, temp_password: str) -> dict:
    return {
        "email": email,
        "password_reset": True,
        "must_change_at_next_login": True,
        "temporary_password_set": bool(temp_password),
        "source": "stub",
    }


def unlock_account(email: str) -> dict:
    return {
        "email": email,
        "unlocked": True,
        "source": "stub",
    }


def get_group_memberships(email: str) -> dict:
    return {
        "email": email,
        "groups": ["Employees", "VPN Users"],
        "source": "stub",
    }


def add_user_to_group(email: str, group_name: str) -> dict:
    return {
        "email": email,
        "group_name": group_name,
        "added": True,
        "source": "stub",
    }


def remove_user_from_group(email: str, group_name: str) -> dict:
    return {
        "email": email,
        "group_name": group_name,
        "removed": True,
        "source": "stub",
    }

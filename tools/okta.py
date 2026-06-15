"""Stub Okta / identity provider tool functions."""


def get_user_factors(email: str) -> dict:
    return {
        "email": email,
        "factors": [
            {"id": "factor_sms_stub", "type": "sms", "status": "active"},
            {"id": "factor_push_stub", "type": "push", "status": "active"},
        ],
        "source": "stub",
    }


def reset_mfa(email: str) -> dict:
    return {
        "email": email,
        "mfa_reset": True,
        "revoked_factors": ["factor_sms_stub", "factor_push_stub"],
        "source": "stub",
    }


def start_mfa_enrollment(email: str, factor_type: str = "push") -> dict:
    return {
        "email": email,
        "factor_type": factor_type,
        "enrollment_started": True,
        "activation_link": "https://example.invalid/stub-mfa-enrollment",
        "source": "stub",
    }


def suspend_user(email: str) -> dict:
    return {
        "email": email,
        "suspended": True,
        "source": "stub",
    }

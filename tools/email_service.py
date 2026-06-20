"""Email notification service using Resend.

Provides both a low-level send function and higher-level helpers
for common helpdesk email scenarios (MFA enrollment, password reset, etc.).
"""

import os

try:
    # pyrefly: ignore [missing-import]
    import resend
    resend.api_key = os.getenv("RESEND_API_KEY")
    _resend_available = True
except ImportError:
    _resend_available = False

FROM_ADDRESS = os.getenv("EMAIL_FROM", "IT Support <onboarding@resend.dev>")


def send_helpdesk_email(to_email: str, subject: str, body_html: str) -> dict:
    """Low-level: send an HTML email via Resend."""
    if not _resend_available:
        return {"status": "failed", "error": "resend package not installed"}

    try:
        params = {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        }
        email_response = resend.Emails.send(params)
        return {
            "status": "dispatched",
            "provider": "resend",
            "id": email_response.get("id"),
        }
    except Exception as e:
        return {"status": "failed", "error": f"[RESEND] {e}"}


def send_mfa_enrollment_email(to_email: str, ticket_url: str) -> dict:
    subject = "Action Required: Set Up Multi-Factor Authentication"
    body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Multi-Factor Authentication Enrollment</h2>
  <p>Your IT support team has initiated MFA enrollment for <strong>{to_email}</strong>.</p>
  <p>Click the button below to set up your authenticator app:</p>
  <p style="text-align: center;">
    <a href="{ticket_url}"
       style="display: inline-block; padding: 12px 24px; background: #0f62fe; color: #fff; text-decoration: none; border-radius: 6px; font-weight: bold;">
       Enroll in MFA
    </a>
  </p>
  <p>If the button does not work, copy and paste this link into your browser:</p>
  <p><a href="{ticket_url}">{ticket_url}</a></p>
  <hr>
  <p style="color: #666; font-size: 12px;">This link expires after one use. If you did not request this, please contact IT support immediately.</p>
</body>
</html>"""
    return send_helpdesk_email(to_email, subject, body)


def send_password_reset_email(to_email: str) -> dict:
    subject = "Password Reset Requested — IT Helpdesk"
    body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Password Reset Requested</h2>
  <p>A password reset has been triggered for <strong>{to_email}</strong>.</p>
  <p>Check your inbox for an email from Auth0 with a link to create a new password. If you do not see it, check your spam folder.</p>
  <p>If you did not request this password reset, please contact IT support immediately — your account may be compromised.</p>
  <hr>
  <p style="color: #666; font-size: 12px;">This is an automated message from the IT Helpdesk system.</p>
</body>
</html>"""
    return send_helpdesk_email(to_email, subject, body)


def send_mfa_reset_notification(to_email: str) -> dict:
    subject = "MFA Reset Complete — Re-enrollment Required"
    body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>MFA Factors Reset</h2>
  <p>Your multi-factor authentication (MFA) factors have been reset for <strong>{to_email}</strong>.</p>
  <p>Please sign in again and re-enroll your authenticator app or phone number when prompted.</p>
  <p>If you did not request this change, please contact IT support immediately — your account may be compromised.</p>
  <hr>
  <p style="color: #666; font-size: 12px;">This is an automated message from the IT Helpdesk system.</p>
</body>
</html>"""
    return send_helpdesk_email(to_email, subject, body)

import os
# pyrefly: ignore [missing-import]
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

def send_helpdesk_email(to_email: str, subject: str, body_html: str) -> dict:
    try:
        params = {
            "from": "IT Support <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        }

        email_response = resend.Emails.send(params)
        
        return {
            "status": "dispatched",
            "provider": "resend",
            "id": email_response.get("id")
        }
        
    except Exception as e:
        print(f"Resend Email Delivery Error: {e}")
        return {"status": "failed", "error": str(e)}
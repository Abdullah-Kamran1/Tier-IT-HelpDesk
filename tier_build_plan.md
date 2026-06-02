# Tier — IT Helpdesk AI: Build Plan

## Stack decision summary

| Concern | Decision | Reason |
|---|---|---|
| AI framework | None — direct Anthropic SDK | Full control, no abstraction overhead, easier debugging |
| Orchestration | One Claude classification call → Python routing logic | Smarter than keywords, simpler than a full agent framework |
| Backend | Python + FastAPI | Async support, great SDK compatibility, you already know Python |
| Task queue | Celery + Redis | Background jobs: bulk CSV import, report generation, SLA checks |
| Database | PostgreSQL | Tickets, audit logs, KB articles, SLA records |
| Cache / session | Redis | Rate limiting, dedup window, classifier result caching |
| Frontend | React + TypeScript + Tailwind | IT manager dashboard and human review queue |
| Messaging | Slack SDK + SendGrid | Inbound tickets and outbound response delivery |

---

## Architecture in one sentence

A FastAPI server receives tickets, calls Claude once to classify them, routes to a specialist Python function that calls Claude again with a scoped prompt, applies a human-in-the-loop gate for flagged cases, then executes tool calls and delivers the response.

No LangGraph. No LangChain. Pure API calls + your own routing logic.

---

## Phase 0 — Foundation (Week 1)

Get the project skeleton in place before any AI code.

### 0.1 Repo and environment
- [ ] Create a GitHub repo: `tier-helpdesk`
- [ ] Set up a Python virtual environment (Python 3.11+)
- [ ] Install core dependencies: `groq fastapi uvicorn psycopg2 python-dotenv pydantic celery redis`
- [ ] Create `.env` for `GROQ_API_KEY`, `DATABASE_URL`, `REDIS_URL`
- [ ] Set up `.gitignore` — never commit `.env`

### 0.2 Project structure
```
tier/
├── api/
│   ├── main.py              # FastAPI app, routes
│   └── dependencies.py      # DB session, auth
├── agents/
│   ├── orchestrator.py      # Classification call
│   ├── identity_access.py   # Password, MFA, VPN specialist
│   ├── device_software.py   # MDM, installs, assets
│   ├── comms_productivity.py# Email, printer, calendar
│   ├── security_triage.py   # Phishing, incidents
│   └── lifecycle.py         # Onboarding, offboarding, SLA
├── tools/
│   ├── active_directory.py  # AD/Graph API wrapper
│   ├── okta.py              # MFA/SSO wrapper
│   ├── itsm.py              # Jira/ServiceNow wrapper
│   └── messaging.py         # Slack/email send
├── models/
│   ├── ticket.py            # SQLAlchemy ticket model
│   ├── audit.py             # Audit log model
│   └── kb_article.py        # KB article model
├── schemas/
│   ├── classification.py    # Pydantic: orchestrator output
│   └── specialist.py        # Pydantic: specialist outputs
├── tasks/
│   └── celery_tasks.py      # Background jobs
├── db/
│   └── migrations/          # Alembic migration files
└── tests/
    ├── test_orchestrator.py
    └── test_specialists.py
```

### 0.3 Database schema (PostgreSQL)

```sql
tickets (
  id UUID PRIMARY KEY,
  channel TEXT,              -- email | slack | api | web | csv
  raw_text TEXT,
  submitter_email TEXT,
  submitted_at TIMESTAMPTZ,
  ticket_type TEXT,
  priority TEXT,             -- P1 | P2 | P3 | P4
  status TEXT,               -- open | in_progress | pending_human | resolved | escalated
  route_to TEXT,
  suspicious_flags TEXT[],
  escalated BOOLEAN,
  resolved_at TIMESTAMPTZ,
  sla_breach BOOLEAN
)

audit_logs (
  id UUID PRIMARY KEY,
  ticket_id UUID REFERENCES tickets(id),
  agent TEXT,                -- orchestrator | identity_access | etc.
  prompt_hash TEXT,
  response_json JSONB,
  created_at TIMESTAMPTZ
)

kb_articles (
  id UUID PRIMARY KEY,
  ticket_id UUID REFERENCES tickets(id),
  title TEXT,
  symptoms TEXT[],
  steps JSONB,
  tags TEXT[],
  status TEXT,               -- draft | published
  created_at TIMESTAMPTZ
)

human_review_queue (
  id UUID PRIMARY KEY,
  ticket_id UUID REFERENCES tickets(id),
  flags TEXT[],
  reviewer TEXT,
  reviewed_at TIMESTAMPTZ,
  decision TEXT              -- approved | rejected
)
```

**Deliverable:** Running FastAPI server, connected to Postgres, returns `{"status": "ok"}` on `GET /health`.

---

## Phase 1 — The Classification Call (Week 2)

This is the core routing logic. Get it right before touching any specialist.

### 1.1 Pydantic schema for orchestrator output

```python
# schemas/classification.py
from pydantic import BaseModel
from typing import Optional

class ClassificationResult(BaseModel):
    ticket_type: str
    priority: str                      # P1 | P2 | P3 | P4
    tier1_capable: bool
    route_to: str
    confidence: float
    suspicious_flags: list[str]
    duplicate_signal: bool
    split_routes: Optional[list[str]]
    escalate_reason: Optional[str]
    classification_notes: str
```

### 1.2 Orchestrator function

```python
# agents/orchestrator.py
import anthropic, json
from schemas.classification import ClassificationResult

SYSTEM_PROMPT = """
You are the classifier for an IT helpdesk AI.
Your ONLY job: read the incoming ticket and return a JSON classification.
Do NOT attempt to solve the problem. Do NOT add prose.

Ticket types:
password_reset | mfa_enrollment | mfa_reset | vpn_issue | email_issue |
printer_issue | software_install | access_request | hardware_issue |
mdm_enrollment | phishing_report | onboarding | offboarding |
license_request | asset_update | general_troubleshooting

Priority:
P1 — multiple users blocked, active security incident
P2 — single user fully blocked, executive affected, hard deadline
P3 — degraded, workaround available
P4 — question, non-urgent request

Escalate immediately (set tier1_capable=false) if:
- requires admin/elevated privileges
- involves a server, switch, or firewall
- indicates data loss or active breach
- outside all defined ticket types

Suspicious flag triggers (add to suspicious_flags list):
- off_hours_request: submitted between 10pm–6am local
- urgency_with_credential_request: urgency language + password/MFA request
- external_sender_domain: sender domain doesn't match company domain
- repeated_reset_pattern: same user reset request 3+ times (check notes field)

Routing:
identity_access    → password_reset, mfa_*, vpn_issue, access_request
device_software    → software_install, hardware_issue, mdm_enrollment, asset_update, license_request
comms_productivity → email_issue, printer_issue
security_triage    → phishing_report, any security incident
lifecycle          → onboarding, offboarding, SLA reporting

For tickets covering multiple issues, set split_routes to a list of specialists.
Respond ONLY with valid JSON matching the schema. No markdown, no explanation.
"""

client = anthropic.Anthropic()

def classify_ticket(ticket_text: str, metadata: dict = {}) -> ClassificationResult:
    user_message = f"Ticket:\n{ticket_text}\n\nMetadata:\n{json.dumps(metadata)}"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text
    data = json.loads(raw)
    return ClassificationResult(**data)
```

### 1.3 Routing dispatcher

```python
# api/main.py (simplified)
from agents.orchestrator import classify_ticket
from agents import identity_access, device_software, comms_productivity, security_triage, lifecycle

SPECIALIST_MAP = {
    "identity_access":     identity_access.handle,
    "device_software":     device_software.handle,
    "comms_productivity":  comms_productivity.handle,
    "security_triage":     security_triage.handle,
    "lifecycle":           lifecycle.handle,
}

async def process_ticket(ticket_text: str, metadata: dict) -> dict:
    classification = classify_ticket(ticket_text, metadata)

    # Write ticket to DB, log classification to audit_log

    if not classification.tier1_capable:
        return escalate(classification)

    if classification.suspicious_flags:
        return queue_for_human_review(classification)

    # Handle split tickets
    routes = classification.split_routes or [classification.route_to]
    results = []
    for route in routes:
        handler = SPECIALIST_MAP[route]
        result = handler(ticket_text, classification)
        results.append(result)

    return merge_and_respond(results)
```

### 1.4 Test the classifier
Write at least 20 test tickets covering:
- Obvious single-type tickets (password reset, printer issue)
- Ambiguous tickets ("I can't get into anything")
- Multi-issue tickets
- Suspicious patterns (off-hours + urgency)
- Clear escalation cases (firewall, server down)
- Edge cases (gibberish, wrong department)

Validate that `ticket_type`, `priority`, and `route_to` are correct for each.

**Deliverable:** `POST /ticket` receives text, returns a correct JSON classification for all 20 test cases.

---

## Phase 2 — First Two Specialists (Week 3)

Build the identity_access and comms_productivity specialists. These cover the highest-volume real-world tickets (password resets, email issues) so you get signal fast.

### 2.1 Specialist pattern — every specialist follows this structure

```python
# agents/identity_access.py
import anthropic, json
from schemas.specialist import IdentityAccessResult

SYSTEM_PROMPT = """
You are the identity and access specialist for an IT helpdesk.
You handle: password resets, MFA enrollment, MFA resets, VPN issues, access requests.

Given a ticket and its classification, produce a complete tier-1 response package.

Return JSON with:
{
  "troubleshooting_steps": [...],      # Plain-language steps for IT staff
  "user_message_draft": "...",         # Friendly message to send the user
  "verification_required": [...],      # Identity checks before acting
  "actions_to_execute": [...],         # Actual tool calls to make
  "kb_draft": { title, symptoms, steps, tags },
  "escalate": false,
  "escalate_reason": null
}

Write troubleshooting steps in plain language a junior IT staff member can follow.
Write user messages in a warm, non-technical tone. Avoid jargon.
Never instruct execution of actions without listing required verification first.
"""

client = anthropic.Anthropic()

def handle(ticket_text: str, classification) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Ticket: {ticket_text}\nClassification: {classification.model_dump_json()}"
        }]
    )
    return json.loads(response.content[0].text)
```

Each of the five specialists is the same pattern — only the system prompt changes.

### 2.2 Specialist system prompts to write in Phase 2
- `identity_access` — password resets with verification steps, MFA flows, VPN tier-1 fixes
- `comms_productivity` — Outlook troubleshooting, printer queue fixes, shared mailbox access

### 2.3 Human review queue endpoint

```
POST /review/{ticket_id}/approve  → release to specialist execution
POST /review/{ticket_id}/reject   → close ticket, notify user
GET  /review/pending              → list all flagged tickets awaiting review
```

**Deliverable:** End-to-end flow for a password reset ticket: receive → classify → specialist → user message draft → logged to DB.

---

## Phase 3 — Remaining Specialists + Tool Stubs (Week 4)

### 3.1 Build remaining three specialists
- `device_software` — MDM enrollment steps, software install guides, asset tracking
- `security_triage` — phishing email analysis, incident initial response, escalation packet
- `lifecycle` — onboarding checklists, offboarding checklists, SLA tracking

### 3.2 Tool layer stubs
Build stub implementations first (return fake data), then wire real APIs later:

```python
# tools/active_directory.py
def get_user(email: str) -> dict:
    # Stub: return { "display_name": "Test User", "locked": True, "last_login": "..." }
    # Real: Microsoft Graph API GET /users/{email}
    pass

def reset_password(email: str, temp_password: str) -> bool:
    # Stub: return True
    # Real: Graph API PATCH /users/{email} { "passwordProfile": { ... } }
    pass

def unlock_account(email: str) -> bool:
    pass
```

Stubs let you test the full pipeline end-to-end before any real credentials.

### 3.3 SLA tracking
Add a Celery beat task that runs every 5 minutes:
```python
@celery.task
def check_sla_breaches():
    # Query open tickets where:
    # P1 > 1 hour old, P2 > 4 hours, P3 > 8 hours, P4 > 3 days
    # Mark sla_breach = True, alert IT manager via Slack
```

**Deliverable:** All five specialists wired up with stub tools. Full ticket lifecycle working end-to-end with fake tool responses.

---

## Phase 4 — Ingestion Channels (Week 5)

Connect the real input sources.

### 4.1 Email ingestion
- Set up a dedicated inbox: `helpdesk@yourcompany.com`
- Use SendGrid Inbound Parse or IMAP polling to receive emails as HTTP webhooks
- Parse sender, subject, body → normalize to ticket schema → call `process_ticket()`

### 4.2 Slack ingestion
- Create a Slack app with a slash command `/ticket` and an Events API listener for DMs
- Any message to the helpdesk bot or `/ticket` submission goes to `process_ticket()`

### 4.3 Web form
- A simple React form: Name, Email, Issue description, Urgency toggle
- `POST /ticket` with the form data

### 4.4 CSV bulk import
```python
# tasks/celery_tasks.py
@celery.task
def bulk_import_csv(file_path: str):
    # Fuzzy column matching: "Subject" | "Issue" | "Description" → ticket_text
    # "Requester" | "User" | "Email" → submitter_email
    # Validate each row, classify and create in DB
    # Return import report: {total, succeeded, failed, errors}
```

**Deliverable:** Tickets flowing in from email, Slack, web form, and CSV upload.

---

## Phase 5 — Real Tool Integrations (Week 6)

Replace stubs with real API calls. Work through these one at a time.

### 5.1 Microsoft Graph API (Active Directory)
- Register an Azure AD app, get client credentials
- Implement: `get_user()`, `reset_password()`, `unlock_account()`, `get_group_memberships()`

### 5.2 Okta / Duo (MFA)
- Implement: `get_user_factors()`, `reset_mfa()`, `enroll_authenticator()`

### 5.3 Jira Service Management (ITSM)
- Implement: `create_ticket()`, `update_ticket()`, `escalate_ticket()`, `add_comment()`

### 5.4 Intune / Jamf (MDM)
- Implement: `get_device()`, `send_enrollment_link()`, `check_compliance_status()`

### 5.5 Slack + SendGrid (Messaging output)
- Implement: `send_user_message()`, `post_to_it_channel()`, `send_outage_notification()`

> **Security rule:** No tool call that modifies anything (reset password, disable account, etc.) executes unless `human_review_queue.decision == "approved"` for flagged tickets. Non-flagged standard tickets can execute tool calls automatically for tier-1 safe operations.

**Deliverable:** Full end-to-end with real APIs on at least one integration (AD recommended as first).

---

## Phase 6 — IT Manager Dashboard (Week 7)

React + TypeScript frontend. This is read-heavy — mostly displaying what the backend already knows.

### 6.1 Pages to build
- **Live queue** — all open tickets, sortable by priority and age, SLA breach indicators
- **Human review queue** — flagged tickets with suspicious indicators, approve/reject buttons
- **Ticket detail** — full classification, specialist output, troubleshooting steps, user message draft, audit trail
- **KB library** — searchable list of auto-drafted articles, publish/edit workflow
- **Weekly report** — ticket volume, FCR rate, SLA compliance, escalation count

### 6.2 Real-time updates
- WebSocket connection from the dashboard to the FastAPI backend
- New tickets and SLA breaches push to the queue in real-time without page refresh

### 6.3 Key components
```
TicketQueue       — filterable table, priority badges, age indicators
TicketDetailPanel — classification JSON, specialist response, action buttons
ReviewPanel       — flagged indicators, approve/reject, add note
KBArticleEditor   — drafted content, tag editor, publish button
ReportView        — metric cards, charts (Recharts)
```

**Deliverable:** Dashboard showing live ticket queue, human review queue functional, ticket detail view with full audit trail.

---

## Phase 7 — Hardening and Launch (Week 8)

### 7.1 Testing
- Unit tests for every specialist: 10+ test tickets each
- Integration tests for every tool wrapper
- End-to-end test: email in → response out
- Adversarial tests: prompt injection attempts in ticket text, malformed CSV, invalid JSON from Claude (add retry + fallback)

### 7.2 Reliability
- Add retry logic on all Claude API calls (exponential backoff, max 3 retries)
- Add fallback for JSON parse failures: if Claude returns malformed JSON, log it, flag for human review, never crash
- Rate limiting on `/ticket` endpoint to prevent abuse

### 7.3 Security
- All API endpoints require an API key or session token
- Audit log is append-only — no deletes, no updates
- Secrets (AD credentials, Okta keys) via environment variables only, never hardcoded
- Review queue enforced at the code level — no bypass path

### 7.4 Deployment
- Dockerize: one container for FastAPI, one for Celery worker, one for Redis, one for Postgres
- `docker-compose.yml` for local development
- Deploy to Railway, Render, or a VPS with Nginx reverse proxy
- Set up basic monitoring: Sentry for errors, uptime check on `/health`

---

## Build order summary

| Week | Phase | What you have at the end |
|------|-------|--------------------------|
| 1 | Foundation | Running FastAPI + Postgres + project structure |
| 2 | Classification | Smart ticket routing working for all ticket types |
| 3 | First specialists | Password reset and email issues fully handled |
| 4 | All specialists + stubs | Full pipeline, fake tools, all ticket types covered |
| 5 | Ingestion channels | Tickets flowing from email, Slack, web, CSV |
| 6 | Real tool integrations | Actual AD resets, real Jira tickets, real Slack messages |
| 7 | Dashboard | IT manager can see queue, review flagged tickets, read KB drafts |
| 8 | Hardening | Tested, secured, deployed, monitored |

---

## What to build on Day 1

1. Create the repo and virtual environment
2. Install dependencies
3. Write `agents/orchestrator.py` with the classification prompt
4. Write `schemas/classification.py` with the Pydantic model
5. Create a simple `test_classify.py` script that sends 5 test tickets and prints the JSON output
6. Verify the classifier returns correct `ticket_type`, `priority`, and `route_to` for each

That's the entire Day 1 scope. Get the classifier working cleanly before touching anything else.

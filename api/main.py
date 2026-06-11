"""FastAPI app + Phase 1.3 routing dispatcher.

Flow:
    POST /ticket
        -> classify_ticket()         (orchestrator, Phase 1.2)
        -> persist ticket + audit log to Postgres
        -> escalate / queue_for_human_review / dispatch to specialist(s)
        -> merge_and_respond()
"""

import hashlib
import json
from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from agents.orchestrator import classify_ticket
from agents import (
    identity_access,
    device_software,
    comms_productivity,
    security_triage,
    lifecycle,
)
from schemas.classification import ClassificationResult
from db.init_db import get_connection


app = FastAPI(
    title="Tier 1 IT Helpdesk API",
    version="1.0.0",
    description="Interactive API docs — try endpoints at /docs (Swagger UI) or /redoc",
)


SPECIALIST_MAP = {
    "identity_access":    identity_access.handle,
    "device_software":    device_software.handle,
    "comms_productivity": comms_productivity.handle,
    "security_triage":    security_triage.handle,
    "lifecycle":          lifecycle.handle,
}


class TicketIn(BaseModel):
    ticket_text: str
    metadata: dict = {}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _persist_ticket(ticket_text: str, metadata: dict, c: ClassificationResult) -> str:
    """Insert the ticket + classification audit row. Returns the new ticket UUID."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tickets (
                        channel, raw_text, submitter_email,
                        ticket_type, priority, status,
                        route_to, suspicious_flags, escalated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        metadata.get("channel", "api"),
                        ticket_text,
                        metadata.get("submitter_email"),
                        c.ticket_type,
                        c.priority,
                        "pending_human" if c.suspicious_flags else
                            ("escalated" if not c.tier1_capable else "in_progress"),
                        c.route_to,
                        c.suspicious_flags,
                        not c.tier1_capable,
                    ),
                )
                ticket_id = cur.fetchone()[0]

                prompt_hash = hashlib.sha256(ticket_text.encode("utf-8")).hexdigest()
                cur.execute(
                    """
                    INSERT INTO audit_logs (ticket_id, agent, prompt_hash, response_json)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (ticket_id, "orchestrator", prompt_hash, json.dumps(c.model_dump())),
                )

                if c.suspicious_flags:
                    cur.execute(
                        """
                        INSERT INTO human_review_queue (ticket_id, flags)
                        VALUES (%s, %s);
                        """,
                        (ticket_id, c.suspicious_flags),
                    )
        return str(ticket_id)
    finally:
        conn.close()


def _log_specialist_response(ticket_id: str, agent_name: str, response: dict) -> None:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (ticket_id, agent, response_json)
                    VALUES (%s, %s, %s);
                    """,
                    (ticket_id, agent_name, json.dumps(response)),
                )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routing branches
# ---------------------------------------------------------------------------

def escalate(ticket_id: str, c: ClassificationResult) -> dict:
    return {
        "ticket_id": ticket_id,
        "status": "escalated",
        "reason": c.escalate_reason or "tier1_capable=false",
        "classification": c.model_dump(),
    }


def queue_for_human_review(ticket_id: str, c: ClassificationResult) -> dict:
    return {
        "ticket_id": ticket_id,
        "status": "pending_human_review",
        "flags": c.suspicious_flags,
        "classification": c.model_dump(),
    }


def merge_and_respond(ticket_id: str, c: ClassificationResult, results: list[dict]) -> dict:
    return {
        "ticket_id": ticket_id,
        "status": "handled",
        "classification": c.model_dump(),
        "specialist_results": results,
    }


# ---------------------------------------------------------------------------
# Core dispatcher
# ---------------------------------------------------------------------------

async def process_ticket(ticket_text: str, metadata: Optional[dict] = None) -> dict:
    metadata = metadata or {}

    classification = classify_ticket(ticket_text, metadata)
    ticket_id = _persist_ticket(ticket_text, metadata, classification)

    if not classification.tier1_capable:
        return escalate(ticket_id, classification)

    if classification.suspicious_flags:
        return queue_for_human_review(ticket_id, classification)

    routes = classification.split_routes or [classification.route_to]
    results: list[dict] = []
    for route in routes:
        handler = SPECIALIST_MAP.get(route)
        if handler is None:
            results.append({"route": route, "error": f"unknown specialist '{route}'"})
            continue
        result = handler(ticket_text, classification)
        _log_specialist_response(ticket_id, route, result)
        results.append({"route": route, "result": result})

    return merge_and_respond(ticket_id, classification, results)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Welcome to the IT Helpdesk AI"}


@app.post("/ticket")
async def submit_ticket(payload: TicketIn):
    try:
        return await process_ticket(payload.ticket_text, payload.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

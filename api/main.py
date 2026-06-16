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
import os
import tempfile
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, Request
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse
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
from tasks.celery_tasks import bulk_import_csv


app = FastAPI(
    title="Tier 1 IT Helpdesk API",
    version="1.0.0",
    description="Interactive API docs — try endpoints at /docs (Swagger UI) or /redoc",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


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


class ReviewDecisionIn(BaseModel):
    reviewer: Optional[str] = None


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


def _dispatch_to_specialists(
    ticket_id: str,
    ticket_text: str,
    c: ClassificationResult,
    metadata: dict | None = None,
) -> list[dict]:
    routes = c.split_routes or [c.route_to]
    results: list[dict] = []
    for route in routes:
        handler = SPECIALIST_MAP.get(route)
        if handler is None:
            results.append({"route": route, "error": f"unknown specialist '{route}'"})
            continue
        result = handler(ticket_text, c, metadata)
        _log_specialist_response(ticket_id, route, result)
        results.append({"route": route, "result": result})
    return results


def _get_ticket_for_review(ticket_id: str) -> tuple[str, dict]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.raw_text, a.response_json
                    FROM tickets t
                    JOIN audit_logs a ON a.ticket_id = t.id
                    WHERE t.id = %s AND a.agent = 'orchestrator'
                    ORDER BY a.created_at DESC
                    LIMIT 1;
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise KeyError(ticket_id)
                return row[0], row[1]
    finally:
        conn.close()


def _mark_review(ticket_id: str, decision: str, reviewer: Optional[str]) -> None:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE human_review_queue
                    SET decision = %s, reviewer = %s, reviewed_at = NOW()
                    WHERE ticket_id = %s AND decision IS NULL;
                    """,
                    (decision, reviewer, ticket_id),
                )
                if cur.rowcount == 0:
                    raise KeyError(ticket_id)
    finally:
        conn.close()


def _update_ticket_status(ticket_id: str, status: str) -> None:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tickets SET status = %s WHERE id = %s;",
                    (status, ticket_id),
                )
    finally:
        conn.close()


def _list_pending_reviews() -> list[dict]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT q.ticket_id, q.flags, t.raw_text, t.priority, t.route_to, t.submitted_at
                    FROM human_review_queue q
                    JOIN tickets t ON t.id = q.ticket_id
                    WHERE q.decision IS NULL
                    ORDER BY t.submitted_at ASC;
                    """
                )
                return [
                    {
                        "ticket_id": str(row[0]),
                        "flags": row[1] or [],
                        "ticket_text": row[2],
                        "priority": row[3],
                        "route_to": row[4],
                        "submitted_at": row[5].isoformat() if row[5] else None,
                    }
                    for row in cur.fetchall()
                ]
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

    results = _dispatch_to_specialists(ticket_id, ticket_text, classification, metadata)

    return merge_and_respond(ticket_id, classification, results)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Tier 1 IT Helpdesk</title>
            <style>
              body {
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                font-family: Arial, sans-serif;
                background: #f6f7f9;
                color: #20242c;
              }
              main {
                width: min(560px, calc(100vw - 32px));
                padding: 28px;
                background: #fff;
                border: 1px solid #d8dde6;
                border-radius: 8px;
              }
              a {
                display: inline-block;
                margin-top: 16px;
                color: #0f62fe;
                font-weight: 700;
              }
            </style>
          </head>
          <body>
            <main>
              <h1>Tier 1 IT Helpdesk</h1>
              <p>Open the web support form to submit a ticket or upload a CSV batch.</p>
              <a href="/web">Go to web support form</a>
            </main>
          </body>
        </html>
        """
    )


@app.get("/web", response_class=HTMLResponse)
def web_support_form():
    try:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="web form not found")


@app.post("/ticket")
async def submit_ticket(payload: TicketIn):
    try:
        return await process_ticket(payload.ticket_text, payload.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ticket/bulk_csv")
async def submit_bulk_csv(request: Request, filename: Optional[str] = None):
    if filename and not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")

    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="CSV body is empty")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            temp_path = temp_file.name
            temp_file.write(content)

        return bulk_import_csv(temp_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


@app.get("/review/pending")
def pending_reviews():
    try:
        return {"pending": _list_pending_reviews()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/review/{ticket_id}/approve")
def approve_review(ticket_id: str, payload: ReviewDecisionIn = ReviewDecisionIn()):
    try:
        ticket_text, raw_classification = _get_ticket_for_review(ticket_id)
        classification = ClassificationResult(**raw_classification)
        _mark_review(ticket_id, "approved", payload.reviewer)
        _update_ticket_status(ticket_id, "in_progress")
        results = _dispatch_to_specialists(ticket_id, ticket_text, classification, {})
        return merge_and_respond(ticket_id, classification, results)
    except KeyError:
        raise HTTPException(status_code=404, detail="pending review ticket not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/review/{ticket_id}/reject")
def reject_review(ticket_id: str, payload: ReviewDecisionIn = ReviewDecisionIn()):
    try:
        _mark_review(ticket_id, "rejected", payload.reviewer)
        _update_ticket_status(ticket_id, "closed_rejected")
        return {"ticket_id": ticket_id, "status": "closed_rejected"}
    except KeyError:
        raise HTTPException(status_code=404, detail="pending review ticket not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

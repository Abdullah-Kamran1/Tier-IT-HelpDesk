import os
import csv
import asyncio
import inspect
from collections.abc import Callable, Awaitable
from typing import Any

# pyrefly: ignore [missing-import]
from celery import Celery

from db.init_db import get_connection
from tools.messaging import notify_manager


celery = Celery(
    "tier_helpdesk",
    broker=os.getenv("CELERY_BROKER_URL", "memory://"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "cache+memory://"),
)

celery.conf.beat_schedule = {
    "check-sla-breaches-every-5-minutes": {
        "task": "tasks.celery_tasks.check_sla_breaches",
        "schedule": 300.0,
    },
}


SLA_HOURS = {
    "P1": 1,
    "P2": 4,
    "P3": 8,
    "P4": 72,
}


TEXT_COLUMN_ALIASES = {
    "ticket_text",
    "ticket text",
    "description",
    "issue",
    "subject",
    "summary",
    "request",
    "details",
}

EMAIL_COLUMN_ALIASES = {
    "submitter_email",
    "submitter email",
    "requester",
    "requester email",
    "user",
    "user email",
    "email",
}

NAME_COLUMN_ALIASES = {
    "name",
    "requester_name",
    "requester name",
    "submitter",
    "submitter name",
}

URGENCY_COLUMN_ALIASES = {
    "urgent",
    "urgency",
    "priority",
}


TicketProcessor = Callable[[str, dict], dict | Awaitable[dict]]


def _normalize_column_name(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _find_column(fieldnames: list[str], aliases: set[str]) -> str | None:
    normalized_aliases = {_normalize_column_name(alias) for alias in aliases}
    for field in fieldnames:
        if _normalize_column_name(field) in normalized_aliases:
            return field
    return None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "y", "1", "urgent", "high", "p1", "p2"}


def _run_processor(processor: TicketProcessor, ticket_text: str, metadata: dict) -> dict:
    result = processor(ticket_text, metadata)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def import_csv_file(file_path: str, processor: TicketProcessor) -> dict:
    """Import a CSV file into tickets using fuzzy column aliases."""
    report = {
        "total": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
        "tickets": [],
    }

    with open(file_path, newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            return {
                **report,
                "failed": 1,
                "errors": [{"row": None, "error": "CSV header row is missing"}],
            }

        text_column = _find_column(fieldnames, TEXT_COLUMN_ALIASES)
        email_column = _find_column(fieldnames, EMAIL_COLUMN_ALIASES)
        name_column = _find_column(fieldnames, NAME_COLUMN_ALIASES)
        urgency_column = _find_column(fieldnames, URGENCY_COLUMN_ALIASES)

        if text_column is None:
            return {
                **report,
                "failed": 1,
                "errors": [
                    {
                        "row": None,
                        "error": "No issue column found. Expected one of: Subject, Issue, Description, ticket_text",
                    }
                ],
            }

        for row_number, row in enumerate(reader, start=2):
            report["total"] += 1
            ticket_text = (row.get(text_column) or "").strip()
            if not ticket_text:
                report["failed"] += 1
                report["errors"].append({"row": row_number, "error": "Ticket text is empty"})
                continue

            metadata = {
                "channel": "csv",
                "source_id": str(row_number),
            }
            if email_column and row.get(email_column):
                metadata["submitter_email"] = row[email_column].strip()
            if name_column and row.get(name_column):
                metadata["submitter_name"] = row[name_column].strip()
            if urgency_column and row.get(urgency_column):
                metadata["urgent"] = _truthy(row[urgency_column])

            try:
                result = _run_processor(processor, ticket_text, metadata)
            except Exception as exc:
                report["failed"] += 1
                report["errors"].append({"row": row_number, "error": str(exc)})
                continue

            report["succeeded"] += 1
            report["tickets"].append(
                {
                    "row": row_number,
                    "ticket_id": result.get("ticket_id"),
                    "status": result.get("status"),
                }
            )

    return report


@celery.task
def check_sla_breaches() -> dict:
    conn = get_connection()
    breached: list[dict] = []
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, priority, submitted_at, route_to
                    FROM tickets
                    WHERE resolved_at IS NULL
                      AND sla_breach = FALSE
                      AND status NOT IN ('closed', 'closed_rejected', 'resolved')
                      AND submitted_at < NOW() - (
                          CASE priority
                              WHEN 'P1' THEN INTERVAL '1 hour'
                              WHEN 'P2' THEN INTERVAL '4 hours'
                              WHEN 'P3' THEN INTERVAL '8 hours'
                              WHEN 'P4' THEN INTERVAL '72 hours'
                              ELSE INTERVAL '8 hours'
                          END
                      );
                    """
                )
                rows = cur.fetchall()
                ticket_ids = [row[0] for row in rows]

                if ticket_ids:
                    cur.execute(
                        """
                        UPDATE tickets
                        SET sla_breach = TRUE
                        WHERE id = ANY(%s);
                        """,
                        (ticket_ids,),
                    )

                breached = [
                    {
                        "ticket_id": str(row[0]),
                        "priority": row[1],
                        "submitted_at": row[2].isoformat() if row[2] else None,
                        "route_to": row[3],
                    }
                    for row in rows
                ]
    finally:
        conn.close()

    for ticket in breached:
        notify_manager(
            message=f"SLA breach detected for ticket {ticket['ticket_id']} ({ticket['priority']}).",
            priority=ticket["priority"] or "P3",
        )

    return {
        "checked": True,
        "breached_count": len(breached),
        "breached_tickets": breached,
        "source": "stub",
    }


@celery.task
def bulk_import_csv(file_path: str) -> dict:
    from api.main import process_ticket

    return import_csv_file(file_path, process_ticket)

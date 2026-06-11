import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS tickets (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel          TEXT,
    raw_text         TEXT,
    submitter_email  TEXT,
    submitted_at     TIMESTAMPTZ DEFAULT NOW(),
    ticket_type      TEXT,
    priority         TEXT,
    status           TEXT DEFAULT 'open',
    route_to         TEXT,
    suspicious_flags TEXT[],
    escalated        BOOLEAN DEFAULT FALSE,
    resolved_at      TIMESTAMPTZ,
    sla_breach       BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id     UUID REFERENCES tickets(id) ON DELETE CASCADE,
    agent         TEXT,
    prompt_hash   TEXT,
    response_json JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_articles (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id  UUID REFERENCES tickets(id) ON DELETE SET NULL,
    title      TEXT,
    symptoms   TEXT[],
    steps      JSONB,
    tags       TEXT[],
    status     TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS human_review_queue (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id   UUID REFERENCES tickets(id) ON DELETE CASCADE,
    flags       TEXT[],
    reviewer    TEXT,
    reviewed_at TIMESTAMPTZ,
    decision    TEXT
);

CREATE INDEX IF NOT EXISTS idx_tickets_status        ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority      ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ticket_id  ON audit_logs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_decision ON human_review_queue(decision);
"""


def get_connection():
    """Return a new psycopg2 connection using DATABASE_URL from the environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file, e.g.\n"
            "  DATABASE_URL=postgresql://user:password@localhost:5432/tier_helpdesk"
        )
    return psycopg2.connect(db_url)


def init_schema() -> None:
    """Create all tables from Phase 0.3 of the build plan."""
    print("Connecting to PostgreSQL...")
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                print("Creating tables: tickets, audit_logs, kb_articles, human_review_queue")
                cur.execute(SCHEMA_SQL)
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                          'tickets', 'audit_logs', 'kb_articles', 'human_review_queue'
                      )
                    ORDER BY table_name;
                    """
                )
                rows = cur.fetchall()
                print(f"Tables present in 'public' schema: {[r[0] for r in rows]}")
        print("Schema initialized successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        init_schema()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

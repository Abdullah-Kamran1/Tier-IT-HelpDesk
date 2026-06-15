"""Stub ITSM tool functions for tickets, tasks, assets, and KB drafts."""


def create_ticket(title: str, description: str, priority: str = "P4") -> dict:
    return {
        "ticket_id": "STUB-TICKET-1001",
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "source": "stub",
    }


def add_comment(ticket_id: str, comment: str, internal: bool = True) -> dict:
    return {
        "ticket_id": ticket_id,
        "comment_added": True,
        "internal": internal,
        "comment": comment,
        "source": "stub",
    }


def update_status(ticket_id: str, status: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "status": status,
        "updated": True,
        "source": "stub",
    }


def assign_ticket(ticket_id: str, assignee: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "assignee": assignee,
        "assigned": True,
        "source": "stub",
    }


def get_asset(asset_tag: str) -> dict:
    return {
        "asset_tag": asset_tag,
        "serial_number": "STUB-SERIAL-001",
        "assigned_to": "test.user@example.com",
        "status": "in_service",
        "warranty_active": True,
        "source": "stub",
    }


def update_asset(asset_tag: str, updates: dict) -> dict:
    return {
        "asset_tag": asset_tag,
        "updated": True,
        "updates": updates,
        "source": "stub",
    }


def create_kb_draft(title: str, symptoms: list[str], steps: list[str], tags: list[str]) -> dict:
    return {
        "kb_id": "STUB-KB-1001",
        "title": title,
        "symptoms": symptoms,
        "steps": steps,
        "tags": tags,
        "status": "draft",
        "source": "stub",
    }

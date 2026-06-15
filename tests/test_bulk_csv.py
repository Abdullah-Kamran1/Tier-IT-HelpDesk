from pathlib import Path

from tasks.celery_tasks import import_csv_file


def test_import_csv_file_maps_fuzzy_columns(tmp_path: Path):
    csv_path = tmp_path / "tickets.csv"
    csv_path.write_text(
        "Subject,Requester,Name,Urgency\n"
        "Reset my Okta MFA,user@example.com,Sam User,yes\n",
        encoding="utf-8",
    )
    calls = []

    def fake_processor(ticket_text: str, metadata: dict) -> dict:
        calls.append((ticket_text, metadata))
        return {"ticket_id": "ticket-1", "status": "handled"}

    report = import_csv_file(str(csv_path), fake_processor)

    assert report["total"] == 1
    assert report["succeeded"] == 1
    assert report["failed"] == 0
    assert report["tickets"] == [{"row": 2, "ticket_id": "ticket-1", "status": "handled"}]
    assert calls == [
        (
            "Reset my Okta MFA",
            {
                "channel": "csv",
                "source_id": "2",
                "submitter_email": "user@example.com",
                "submitter_name": "Sam User",
                "urgent": True,
            },
        )
    ]


def test_import_csv_file_reports_missing_issue_column(tmp_path: Path):
    csv_path = tmp_path / "tickets.csv"
    csv_path.write_text("Requester\nuser@example.com\n", encoding="utf-8")

    report = import_csv_file(str(csv_path), lambda _text, _metadata: {})

    assert report["total"] == 0
    assert report["succeeded"] == 0
    assert report["failed"] == 1
    assert "No issue column found" in report["errors"][0]["error"]


def test_import_csv_file_continues_after_row_error(tmp_path: Path):
    csv_path = tmp_path / "tickets.csv"
    csv_path.write_text(
        "Issue,Email\n"
        ",empty@example.com\n"
        "Laptop will not boot,user@example.com\n",
        encoding="utf-8",
    )

    report = import_csv_file(
        str(csv_path),
        lambda _text, _metadata: {"ticket_id": "ticket-2", "status": "handled"},
    )

    assert report["total"] == 2
    assert report["succeeded"] == 1
    assert report["failed"] == 1
    assert report["errors"] == [{"row": 2, "error": "Ticket text is empty"}]

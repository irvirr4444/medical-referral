from __future__ import annotations

import http.client
import json
import threading

from Outlook.mail import InboundPdfMetadata
from referral_pipeline.api.intake_inbox import IntakeInboxFeed
from referral_pipeline.api.server import _parse_limit, create_server


class _GraphClient:
    def __init__(self) -> None:
        self.calls = 0

    def list_inbox_pdf_metadata(self, *, max_messages: int):
        self.calls += 1
        assert max_messages == 10
        return [
            InboundPdfMetadata(
                message_id="message-1",
                attachment_id="attachment-1",
                filename="referral.pdf",
                received_at="2026-08-12T08:30:00Z",
                subject="New referral",
                sender="sender@example.test",
            )
        ]

    def download_pdf_attachment(self, metadata: InboundPdfMetadata):
        from Outlook.mail import InboundPdfAttachment

        return InboundPdfAttachment(
            source="outlook-graph",
            message_id=metadata.message_id,
            attachment_id=metadata.attachment_id,
            filename=metadata.filename,
            content=b"%PDF-1.4\ntest",
        )


def test_inbox_feed_projects_metadata_without_pdf_content() -> None:
    client = _GraphClient()
    feed = IntakeInboxFeed(lambda: client, cache_ttl_seconds=30, clock=lambda: 10.0)

    first = feed.read(limit=10)
    second = feed.read(limit=10)

    assert client.calls == 1
    assert first["connected"] is True
    assert first["source"] == "testing-infobox"
    assert first["referrals"] == second["referrals"]
    assert first["referrals"][0] == {
        "id": "21f6fcf107129b8e",
        "filename": "referral.pdf",
        "subject": "New referral",
        "sender": "sender@example.test",
        "received_at": "2026-08-12T08:30:00Z",
        "source": "testing-infobox",
        "status": "pending_extraction",
        "case_id": None,
        "steps": {},
    }
    assert "content" not in first["referrals"][0]

    filename, content = feed.read_pdf(first["referrals"][0]["id"])
    assert filename == "referral.pdf"
    assert content.startswith(b"%PDF-")


def test_inbox_api_limit_is_bounded() -> None:
    assert _parse_limit("1") == 1
    assert _parse_limit("25") == 25

    for invalid in ("0", "26", "many"):
        try:
            _parse_limit(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid limit to fail: {invalid}")


def test_inbox_api_cannot_bind_publicly_without_authentication() -> None:
    try:
        create_server(host="0.0.0.0", port=0, feed=IntakeInboxFeed(lambda: _GraphClient()))
    except ValueError as error:
        assert "local-only" in str(error)
    else:
        raise AssertionError("Expected public binding to be rejected")


def test_inbox_api_exposes_local_monitor_controls() -> None:
    class FakeMonitor:
        def __init__(self) -> None:
            self.state = "stopped"

        def status(self):
            return {"available": True, "state": self.state, "enabled": self.state == "monitoring"}

        def start(self):
            self.state = "monitoring"
            return self.status()

        def stop(self, *, wait: bool = False):
            assert wait is False
            self.state = "stopped"
            return self.status()

    monitor = FakeMonitor()
    server = create_server(
        host="127.0.0.1",
        port=0,
        feed=IntakeInboxFeed(lambda: _GraphClient()),
        monitor=monitor,  # type: ignore[arg-type]
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", "/api/intake/monitor")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["state"] == "stopped"

        connection.request(
            "POST",
            "/api/intake/monitor/start",
            body="{}",
            headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["state"] == "monitoring"

        connection.request(
            "POST",
            "/api/intake/monitor/stop",
            body="{}",
            headers={"Content-Type": "application/json", "Origin": "https://not-local.example"},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

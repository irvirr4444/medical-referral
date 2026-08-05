from __future__ import annotations

import base64

from Outlook.graph import GRAPH_ROOT, OutlookGraphClient, OutlookGraphConfig


def _pdf_b64() -> str:
    return base64.b64encode(b"%PDF-1.4\nsynthetic").decode()


def test_outlook_adapter_accepts_only_real_pdf_attachments(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    valid_pdf = b"%PDF-1.4\nsynthetic"
    monkeypatch.setattr(
        client,
        "_get",
        lambda _path: {
            "value": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "id": "good",
                    "name": "referral.pdf",
                    "contentBytes": base64.b64encode(valid_pdf).decode(),
                },
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "id": "wrong-extension",
                    "name": "referral.txt",
                    "contentBytes": base64.b64encode(valid_pdf).decode(),
                },
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "id": "wrong-content",
                    "name": "not-really.pdf",
                    "contentBytes": base64.b64encode(b"not a pdf").decode(),
                },
            ]
        },
    )

    attachments = client._pdf_attachments_for_message({"id": "message-1", "subject": "Synthetic"})

    assert [(item.attachment_id, item.filename, item.content) for item in attachments] == [("good", "referral.pdf", valid_pdf)]


def test_outlook_adapter_applies_durable_ledger_predicate(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    messages = [
        {"id": "replied", "conversationId": "conversation-1", "hasAttachments": True},
        {"id": "not-replied", "conversationId": "conversation-2", "hasAttachments": True},
    ]
    monkeypatch.setattr(client, "_iter_inbox_messages", lambda **_kwargs: iter(messages))
    inspected = []
    monkeypatch.setattr(
        client,
        "_pdf_attachments_for_message",
        lambda message: inspected.append(message["id"])
        or [
            type("A", (), {"message_id": message["id"]})(),
        ],
    )

    attachments = client.list_inbox_pdf_attachments(
        max_messages=10,
        include_attachment=lambda item: item.message_id == "not-replied",
    )

    assert inspected == ["replied", "not-replied"]
    assert [item.message_id for item in attachments] == ["not-replied"]


def test_list_inbox_paginates_and_counts_eligible_new_messages(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    pages = {
        f"{GRAPH_ROOT}/users/inbox@example.test/mailFolders/inbox/messages?": {
            "value": [
                {
                    "id": "replied",
                    "conversationId": "c1",
                    "hasAttachments": True,
                    "receivedDateTime": "2026-08-05T12:00:00Z",
                    "subject": "Old replied",
                },
                {
                    "id": "eligible-1",
                    "conversationId": "c2",
                    "hasAttachments": True,
                    "receivedDateTime": "2026-08-05T11:00:00Z",
                    "subject": "Eligible one",
                },
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/next-page",
        },
        "https://graph.microsoft.com/v1.0/next-page": {
            "value": [
                {
                    "id": "no-pdf",
                    "conversationId": "c3",
                    "hasAttachments": True,
                    "receivedDateTime": "2026-08-05T10:00:00Z",
                    "subject": "No pdf",
                },
                {
                    "id": "eligible-2",
                    "conversationId": "c4",
                    "hasAttachments": True,
                    "receivedDateTime": "2026-08-05T09:00:00Z",
                    "subject": "Eligible two",
                },
                {
                    "id": "eligible-3",
                    "conversationId": "c5",
                    "hasAttachments": True,
                    "receivedDateTime": "2026-08-05T08:00:00Z",
                    "subject": "Eligible three unused",
                },
            ]
        },
    }

    def fake_get_url(url: str):
        for prefix, payload in pages.items():
            if url.startswith(prefix) or url == prefix:
                return payload
        if "/attachments" in url:
            message_id = url.split("/messages/")[1].split("/")[0]
            if message_id == "no-pdf":
                return {"value": []}
            return {
                "value": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "id": f"att-{message_id}",
                        "name": f"{message_id}.pdf",
                        "contentBytes": _pdf_b64(),
                    }
                ]
            }
        raise AssertionError(url)

    monkeypatch.setattr(client, "_get_url", fake_get_url)
    monkeypatch.setattr(client, "_token", lambda: "token")

    attachments = client.list_inbox_pdf_attachments(
        max_messages=2,
        include_attachment=lambda item: item.message_id != "replied",
    )

    assert [item.message_id for item in attachments] == ["eligible-2", "eligible-1"]
    assert [item.filename for item in attachments] == ["eligible-2.pdf", "eligible-1.pdf"]

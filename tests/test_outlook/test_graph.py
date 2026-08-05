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


def test_outlook_adapter_only_reads_threads_mailbox_has_not_replied_to(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    messages = [
        {"id": "replied", "conversationId": "conversation-1", "hasAttachments": True},
        {"id": "not-replied", "conversationId": "conversation-2", "hasAttachments": True},
    ]
    monkeypatch.setattr(client, "_iter_inbox_messages", lambda **_kwargs: iter(messages))
    monkeypatch.setattr(
        client,
        "_has_mailbox_reply",
        lambda message: message["conversationId"] == "conversation-1",
    )
    inspected = []
    monkeypatch.setattr(
        client,
        "_pdf_attachments_for_message",
        lambda message: inspected.append(message["id"])
        or [
            type("A", (), {"message_id": message["id"]})(),
        ],
    )

    client.list_inbox_pdf_attachments(max_messages=10)

    assert inspected == ["not-replied"]


def test_mailbox_reply_check_queries_sent_items_conversation(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    requested = []
    monkeypatch.setattr(
        client,
        "_get",
        lambda path: requested.append(path) or {"value": [{"id": "sent-reply"}]},
    )

    assert client._has_mailbox_reply({"conversationId": "conversation-1"}) is True
    assert "/mailFolders/sentitems/messages?" in requested[0]
    assert "conversationId+eq+%27conversation-1%27" in requested[0]


def test_list_inbox_paginates_and_counts_eligible_unreplied_messages(monkeypatch) -> None:
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
        if "sentitems" in url:
            if "conversation-c1" in url or "c1" in url:
                # First message is replied; detect by conversation id in filter.
                if "c1" in url and "c2" not in url and "c4" not in url and "c5" not in url:
                    return {"value": [{"id": "sent"}]}
            return {"value": []}
        raise AssertionError(url)

    monkeypatch.setattr(client, "_get_url", fake_get_url)
    monkeypatch.setattr(client, "_token", lambda: "token")

    # More precise reply check using conversationId from the message itself.
    monkeypatch.setattr(
        client,
        "_has_mailbox_reply",
        lambda message: message["conversationId"] == "c1",
    )

    attachments = client.list_inbox_pdf_attachments(max_messages=2)

    assert [item.message_id for item in attachments] == ["eligible-2", "eligible-1"]
    assert [item.filename for item in attachments] == ["eligible-2.pdf", "eligible-1.pdf"]

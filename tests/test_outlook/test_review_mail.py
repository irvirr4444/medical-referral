from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
from Outlook.review_mail import OutlookReviewMailbox


def test_review_mail_replies_with_html_body(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    posted = []
    monkeypatch.setattr(client, "post_no_content", lambda path, payload: posted.append((path, payload)))

    OutlookReviewMailbox(client).send_reply(
        source_message_id="source-message",
        recipient="reviewer@example.test",
        html_body="<p>Body</p>",
        text_body="Body",
        content_type="HTML",
    )

    assert posted[0][0] == "/users/inbox@example.test/messages/source-message/reply"
    assert posted[0][1]["message"]["toRecipients"][0]["emailAddress"]["address"] == "reviewer@example.test"
    assert posted[0][1]["message"]["body"] == {"contentType": "HTML", "content": "<p>Body</p>"}


def test_review_mail_can_resend_legacy_plain_text(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    posted = []
    monkeypatch.setattr(client, "post_no_content", lambda path, payload: posted.append((path, payload)))

    OutlookReviewMailbox(client).send_reply(
        source_message_id="source-message",
        recipient="reviewer@example.test",
        text_body="Body",
        content_type="Text",
    )

    assert posted[0][1]["message"]["body"] == {"contentType": "Text", "content": "Body"}


def test_review_mail_uses_unique_reply_body(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    monkeypatch.setattr(
        client,
        "get_json",
        lambda _path: {
            "value": [
                {
                    "id": "message-1",
                    "subject": "Re: review",
                    "receivedDateTime": "2026-08-04T10:00:00Z",
                    "from": {"emailAddress": {"address": "reviewer@example.test"}},
                    "conversationId": "conversation-1",
                    "uniqueBody": {"content": "<p>CONFIRMED review_abc123_xyz987 abcdefghijklmnop</p>"},
                }
            ]
        },
    )

    replies = OutlookReviewMailbox(client).list_replies(max_messages=10)

    assert replies[0].text == "CONFIRMED review_abc123_xyz987 abcdefghijklmnop"

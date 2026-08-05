from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
from Outlook.review_mail import OutlookReviewMailbox


def test_review_mail_sends_from_configured_mailbox(monkeypatch) -> None:
    client = OutlookGraphClient(OutlookGraphConfig("tenant", "client", "secret", "inbox@example.test"))
    posted = []
    monkeypatch.setattr(client, "post_no_content", lambda path, payload: posted.append((path, payload)))

    OutlookReviewMailbox(client).send(
        recipient="reviewer@example.test",
        subject="Review",
        text_body="Body",
    )

    assert posted[0][0] == "/users/inbox@example.test/sendMail"
    assert posted[0][1]["message"]["toRecipients"][0]["emailAddress"]["address"] == "reviewer@example.test"


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

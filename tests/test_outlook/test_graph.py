from __future__ import annotations

import base64

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig


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

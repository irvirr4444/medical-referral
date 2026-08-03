from __future__ import annotations

from inbox_state import InboxState
from inbound_mail import InboundPdfAttachment


def test_inbox_state_prevents_reprocessing_same_attachment(tmp_path) -> None:
    attachment = InboundPdfAttachment("eml", "message-1", "attachment-1", "referral.pdf", b"%PDF-1.4")
    state = InboxState(tmp_path / "state.sqlite")

    assert not state.is_completed(attachment)
    state.mark(attachment, status="completed")
    assert state.is_completed(attachment)

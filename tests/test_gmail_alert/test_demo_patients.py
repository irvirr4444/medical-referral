from __future__ import annotations

from gmail_alert.demo_patients import demo_for_action
from gmail_alert.feed_bodies import feed_body_for
from gmail_alert.ids import ACTION_IDS
from gmail_alert.render import render_alert
from gmail_alert.send_all import context_for


def test_each_alert_uses_seed_patient() -> None:
    expected = {
        "confirm-intake-review": "gonzalez-eric",
        "confirm-partner-contacted": "butler-alva",
        "cm-assigned": "marcus-feldman",
        "use-fallback-provider": "maria-alvarez",
        "no-area-provider": "betty-hayes",
        "send-referral-provider": "maria-alvarez",
        "eod-follow-up-cm": "thomas-reed",
        "eod-escalate": "frank-owens",
        "not-seen-week-1": "patricia-johnson",
        "not-seen-week-2": "margaret-ellis",
        "not-seen-week-3": "walter-grant",
    }
    assert set(expected) == set(ACTION_IDS)
    for action_id, patient_id in expected.items():
        patient = demo_for_action(action_id)
        assert patient.patient_id == patient_id
        context = context_for(patient, action_id)
        assert context.patient_id == patient_id
        assert context.feed_fields == feed_body_for(action_id)


def test_intake_review_email_uses_gonzalez_platform_fields() -> None:
    patient = demo_for_action("confirm-intake-review")
    rendered = render_alert("confirm-intake-review", context_for(patient, "confirm-intake-review"))
    assert rendered.subject == "Immediate attention · Eric Gonzalez"
    assert "Wound or clinical information: Right groin unstageable pressure injury / wound cellulitis" in rendered.body_text
    assert "[ Confirm all information is correct ]" in rendered.body_text
    assert "OVERDUE" not in rendered.body_text
    assert 'href="#"' in rendered.body_html

from __future__ import annotations

from gmail_alert.catalog import ALERT_TEMPLATES
from gmail_alert.feed_bodies import feed_body_for
from gmail_alert.ids import ACTION_IDS
from gmail_alert.models import AlertContext
from gmail_alert.render import format_late, open_step_url, person_name, render_alert


def test_catalog_covers_every_action_id() -> None:
    assert set(ALERT_TEMPLATES) == set(ACTION_IDS)
    assert len(ACTION_IDS) == 11
    decide = notify = 0
    for template in ALERT_TEMPLATES.values():
        assert template.label
        assert template.reason
        assert "—" not in template.reason
        assert " - " not in template.reason
        assert template.stage_label
        assert template.sla_label
        assert template.kind in ("decide", "notify")
        if template.kind == "decide":
            decide += 1
        else:
            notify += 1
    assert decide == 3
    assert notify == 8


def test_management_notify_cases() -> None:
    management = [
        action_id
        for action_id, template in ALERT_TEMPLATES.items()
        if "management" in template.to_roles
    ]
    assert set(management) == {
        "no-area-provider",
        "eod-escalate",
        "not-seen-week-3",
    }
    for action_id in management:
        assert ALERT_TEMPLATES[action_id].kind == "notify"
        rendered = render_alert(
            action_id,  # type: ignore[arg-type]
            AlertContext(
                patient_id="x",
                patient_name="Test Patient",
                hours_overdue=1,
                open_url="unused",
                feed_fields=feed_body_for(action_id),  # type: ignore[arg-type]
            ),
        )
        assert 'href="#"' not in rendered.body_html


def test_feed_body_for_every_action() -> None:
    for action_id in ACTION_IDS:
        fields = feed_body_for(action_id)
        assert fields
        assert all(label and value for label, value in fields)


def test_person_name() -> None:
    assert person_name("BUTLER, ALVA") == "Alva Butler"
    assert person_name("Gonzalez, Eric") == "Eric Gonzalez"
    assert person_name("Marcus Feldman") == "Marcus Feldman"


def test_format_late() -> None:
    assert format_late(22 / 60) == "22 min"
    assert format_late(0.3) == "18 min"
    assert format_late(26) == "26 hr"
    assert format_late(1.5) == "90 min"


def test_open_step_url() -> None:
    url = open_step_url(ALERT_TEMPLATES["confirm-intake-review"], "pat-1", base_url="https://app.example")
    assert url == "https://app.example/automation?patient=pat-1&stage=intake&step=extract-and-verify"


def test_decide_email_has_cta_and_reason() -> None:
    template = ALERT_TEMPLATES["confirm-intake-review"]
    fields = feed_body_for("confirm-intake-review")
    rendered = render_alert(
        "confirm-intake-review",
        AlertContext(
            patient_id="gonzalez-eric",
            patient_name="Gonzalez, Eric",
            hours_overdue=22 / 60,
            open_url=open_step_url(template, "gonzalez-eric"),
            feed_fields=fields,
        ),
    )
    assert rendered.subject == "Immediate attention · Eric Gonzalez"
    assert rendered.body_text.startswith("Eric Gonzalez\n")
    assert "OVERDUE" not in rendered.body_text
    assert "chart isn’t confirmed" in rendered.body_text.lower() or "chart isn't confirmed" in rendered.body_text.lower()
    assert "nothing can move" in rendered.body_text.lower()
    assert "[ Confirm all information is correct ]" in rendered.body_text
    assert 'href="#"' in rendered.body_html
    assert "http://localhost" not in rendered.body_html


def test_notify_email_has_no_cta() -> None:
    fields = feed_body_for("not-seen-week-3")
    rendered = render_alert(
        "not-seen-week-3",
        AlertContext(
            patient_id="walter-grant",
            patient_name="Walter Grant",
            hours_overdue=2,
            open_url="unused",
            feed_fields=fields,
        ),
    )
    assert "discharge" in rendered.body_text.lower()
    assert "3 weeks" in rendered.body_text
    assert not any(line.startswith("[ ") and line.endswith(" ]") for line in rendered.body_text.splitlines())
    assert 'href="#"' not in rendered.body_html
    assert ALERT_TEMPLATES["not-seen-week-3"].to_roles == ("management",)


def test_eod_follow_up_is_notify_to_cm() -> None:
    template = ALERT_TEMPLATES["eod-follow-up-cm"]
    assert template.kind == "notify"
    assert template.to_roles == ("assigned_cm",)
    rendered = render_alert(
        "eod-follow-up-cm",
        AlertContext(
            patient_id="thomas-reed",
            patient_name="Thomas Reed",
            hours_overdue=24,
            open_url="unused",
            feed_fields=feed_body_for("eod-follow-up-cm"),
        ),
    )
    assert "still isn’t scheduled" in rendered.body_text.lower() or "still isn't scheduled" in rendered.body_text.lower()
    assert 'href="#"' not in rendered.body_html


def test_cm_assigned_handoff_notify() -> None:
    template = ALERT_TEMPLATES["cm-assigned"]
    assert template.kind == "notify"
    assert template.to_roles == ("assigned_cm",)
    rendered = render_alert(
        "cm-assigned",
        AlertContext(
            patient_id="marcus-feldman",
            patient_name="Marcus Feldman",
            hours_overdue=0,
            open_url="unused",
            feed_fields=feed_body_for("cm-assigned"),
        ),
    )
    assert rendered.subject == "New assignment · Marcus Feldman"
    assert rendered.body_text.startswith("Marcus Feldman\n")
    assert "This patient is yours" in rendered.body_text
    assert "ASSIGNED" not in rendered.body_text
    assert "OVERDUE" not in rendered.body_text
    assert "Cole Winfield" in rendered.body_text
    assert "Select provider" in rendered.body_text
    assert 'href="#"' not in rendered.body_html


def test_send_referral_provider_notify() -> None:
    template = ALERT_TEMPLATES["send-referral-provider"]
    assert template.kind == "notify"
    assert template.to_roles == ("provider",)
    assert "assigned_cm" in template.cc_roles
    rendered = render_alert(
        "send-referral-provider",
        AlertContext(
            patient_id="maria-alvarez",
            patient_name="Maria Alvarez",
            hours_overdue=0,
            open_url="unused",
            feed_fields=feed_body_for("send-referral-provider"),
        ),
    )
    assert rendered.subject == "New referral · Maria Alvarez"
    assert rendered.body_text.startswith("Maria Alvarez\n")
    assert "referral packet is ready" in rendered.body_text.lower()
    assert "SENT" not in rendered.body_text
    assert "OVERDUE" not in rendered.body_text
    assert "Daniel Rowady" in rendered.body_text
    assert 'href="#"' not in rendered.body_html

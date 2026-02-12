from bonsai_schemas.audit import Actor, EventCreate, EventSeverity, Subject
from bonsai_schemas.notification import EmailCreate
import datetime as dt


def test_event_create_roundtrip():
    actor = Actor(type="user", id="user_1")
    subject = Subject(type="system", id="sample_1")
    ev = EventCreate(
        source_service="bonsai_api",
        event_type="TEST",
        occurred_at=dt.datetime.now(dt.timezone.utc),
        severity=EventSeverity.INFO,
        actor=actor,
        subject=subject,
    )
    data = ev.model_dump()
    ev2 = EventCreate.model_validate(data)
    assert ev2.source_service == ev.source_service


def test_email_schema():
    em = EmailCreate(subject="hi", recipients=["a@b.com"], body="hello")
    assert em.recipients[0] == "a@b.com"

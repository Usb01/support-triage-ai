from pathlib import Path

from triage import sources
from triage.pipeline import Pipeline
from triage.store import Store

DATA = Path(__file__).resolve().parent.parent / "data"


def test_csv_sample_loads():
    tickets = sources.from_csv(DATA / "sample_tickets.csv")
    assert len(tickets) == 30 and tickets[0].id == "T-1001"


def test_eml_strips_quoted_reply():
    t = sources.from_eml((DATA / "reply_example.eml").read_bytes())
    assert t.customer == "Lina Haddad" and t.email == "lina.haddad@example.com"
    assert "reissue" in t.body and "updated your billing" not in t.body


def test_zendesk_payload():
    t = sources.from_zendesk({"ticket": {"id": 812, "subject": "Login issue", "description": "Can't sign in",
                                         "requester": {"name": "Omar", "email": "o@example.com"},
                                         "created_at": "2026-10-20T08:00:00Z"}})
    assert t.id == "ZD-812" and t.created_at.tzinfo is not None


def test_shift_to_now_keeps_spacing():
    tickets = sources.shift_to_now(sources.from_csv(DATA / "sample_tickets.csv"))
    gaps = sorted(t.created_at for t in tickets)
    assert gaps[-1] > gaps[0]


def test_store_is_idempotent_and_review_updates(tmp_path):
    store, pipe = Store(str(tmp_path / "t.db")), Pipeline("rules")
    t = sources.from_csv(DATA / "sample_tickets.csv")[0]
    assert store.save(pipe.run(t)) is True
    assert store.save(pipe.run(t)) is False
    store.review(t.id, "Edited reply", "approved", priority="urgent", team="Finance")
    row = store.get(t.id)
    assert row["status"] == "approved" and row["final_reply"] == "Edited reply" and row["priority"] == "urgent"


def test_webhook(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGE_DB", str(tmp_path / "w.db"))
    monkeypatch.setenv("WEBHOOK_TOKEN", "s3cret")
    import importlib

    import triage.webhook as wh
    importlib.reload(wh)
    from fastapi.testclient import TestClient
    c = TestClient(wh.app)
    body = {"id": "W-1", "subject": "Charged twice", "body": "I was charged twice"}
    assert c.post("/tickets", json=body).status_code == 401
    r = c.post("/tickets", json=body, headers={"x-webhook-token": "s3cret"}).json()
    assert r["category"] == "billing" and r["team"] == "Finance" and r["duplicate"] is False

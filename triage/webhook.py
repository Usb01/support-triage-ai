"""Small HTTP intake so a helpdesk can push tickets in real time.

    uvicorn triage.webhook:app --port 8001
    POST /tickets          {"id": "...", "subject": "...", "body": "..."}
    POST /zendesk          Zendesk webhook payload
"""
import hmac
import os

from fastapi import FastAPI, Header, HTTPException, Request

from .models import Ticket
from .pipeline import Pipeline
from .sources import from_zendesk
from .store import Store

app = FastAPI(title="Support triage intake")
pipe = Pipeline()
store = Store(os.getenv("TRIAGE_DB", "triage.db"))


def _check(token: str | None):
    expected = os.getenv("WEBHOOK_TOKEN")
    if expected and not (token and hmac.compare_digest(token, expected)):
        raise HTTPException(401, "bad token")


def _handle(ticket: Ticket) -> dict:
    r = pipe.run(ticket)
    created = store.save(r)
    return {"id": ticket.id, "duplicate": not created, "category": r.triage.category, "priority": r.triage.priority,
            "team": r.team, "due_at": r.due_at.isoformat(), "needs_review": r.needs_review, "engine": r.engine}


@app.post("/tickets")
def create(ticket: Ticket, x_webhook_token: str | None = Header(default=None)):
    _check(x_webhook_token)
    return _handle(ticket)


@app.post("/zendesk")
async def zendesk(request: Request, x_webhook_token: str | None = Header(default=None)):
    _check(x_webhook_token)
    return _handle(from_zendesk(await request.json()))

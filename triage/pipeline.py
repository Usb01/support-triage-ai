"""Ticket in → triaged ticket out (classification, team, SLA deadline, draft)."""
import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from . import llm, rules
from .models import Ticket, Triage

TEAMS = {
    "billing": "Finance",
    "technical": "Tier 2 – Engineering",
    "account": "Tier 1 – Support",
    "security": "Security",
    "shipping": "Logistics",
    "feature_request": "Product",
    "general": "Tier 1 – Support",
}

# first-response targets in business hours
SLA_HOURS = {"urgent": 1, "high": 4, "normal": 8, "low": 24}

# Sunday–Thursday 08:00–17:00 (Riyadh, UTC+3)
TZ = timezone(timedelta(hours=3))
WORKDAYS = {6, 0, 1, 2, 3}  # Python weekday(): Mon=0 … Sun=6
OPEN, CLOSE = time(8), time(17)


@dataclass
class Result:
    ticket: Ticket
    triage: Triage
    team: str
    due_at: datetime
    engine: str            # rules | openai | anthropic
    needs_review: bool
    fallback_reason: str | None = None


def add_business_hours(start: datetime, hours: float) -> datetime:
    """Urgent tickets run on the clock 24/7; everything else counts working hours only."""
    t = start.astimezone(TZ)
    remaining = timedelta(hours=hours)
    while remaining > timedelta(0):
        if t.weekday() not in WORKDAYS or t.time() >= CLOSE:
            t = datetime.combine(t.date() + timedelta(days=1), OPEN, TZ)
            continue
        if t.time() < OPEN:
            t = datetime.combine(t.date(), OPEN, TZ)
        end_of_day = datetime.combine(t.date(), CLOSE, TZ)
        step = min(remaining, end_of_day - t)
        t += step
        remaining -= step
    return t


def sla_due(priority: str, created: datetime) -> datetime:
    if priority == "urgent":
        return created.astimezone(TZ) + timedelta(hours=SLA_HOURS["urgent"])
    return add_business_hours(created, SLA_HOURS[priority])


class Pipeline:
    def __init__(self, engine: str | None = None, review_threshold: float = 0.7):
        self.engine = (engine or os.getenv("TRIAGE_ENGINE", "rules")).lower()
        self.review_threshold = review_threshold

    def run(self, ticket: Ticket) -> Result:
        created = ticket.created_at or datetime.now(TZ)
        if created.tzinfo is None:
            created = created.replace(tzinfo=TZ)

        engine, fallback = "rules", None
        if self.engine in ("openai", "anthropic"):
            try:
                fn = llm.classify_openai if self.engine == "openai" else llm.classify_anthropic
                result = fn(ticket)
                engine = self.engine
            except llm.LLMError as exc:
                result, fallback = rules.classify(ticket), str(exc)
        else:
            result = rules.classify(ticket)

        needs_review = (
            result.confidence < self.review_threshold
            or result.priority == "urgent"
            or result.sentiment == "negative"
            or fallback is not None
        )
        return Result(ticket, result, TEAMS[result.category], sla_due(result.priority, created), engine,
                      needs_review, fallback)

import json
import sqlite3
from datetime import datetime, timezone

from .pipeline import Result

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id           TEXT PRIMARY KEY,
    subject      TEXT,
    body         TEXT NOT NULL,
    customer     TEXT,
    email        TEXT,
    channel      TEXT,
    created_at   TEXT NOT NULL,
    category     TEXT NOT NULL,
    priority     TEXT NOT NULL,
    sentiment    TEXT NOT NULL,
    language     TEXT NOT NULL,
    summary      TEXT NOT NULL,
    draft_reply  TEXT NOT NULL,
    confidence   REAL NOT NULL,
    reasons      TEXT NOT NULL,
    team         TEXT NOT NULL,
    due_at       TEXT NOT NULL,
    engine       TEXT NOT NULL,
    needs_review INTEGER NOT NULL,
    fallback     TEXT,
    status       TEXT NOT NULL DEFAULT 'open',   -- open | approved | sent | closed
    final_reply  TEXT,
    reviewed_at  TEXT
);
"""


class Store:
    def __init__(self, path: str = "triage.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def save(self, r: Result) -> bool:
        """Insert a triaged ticket. Returns False if the ticket id already exists."""
        t, x = r.ticket, r.triage
        created = (t.created_at or datetime.now(timezone.utc)).isoformat()
        with self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO tickets (id, subject, body, customer, email, channel, created_at, category, "
                "priority, sentiment, language, summary, draft_reply, confidence, reasons, team, due_at, engine, "
                "needs_review, fallback) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t.id, t.subject, t.body, t.customer, t.email, t.channel, created, x.category, x.priority,
                 x.sentiment, x.language, x.summary, x.draft_reply, x.confidence, json.dumps(x.reasons), r.team,
                 r.due_at.isoformat(), r.engine, int(r.needs_review), r.fallback_reason),
            )
        return cur.rowcount == 1

    def review(self, ticket_id: str, reply: str, status: str = "approved", **changes) -> None:
        allowed = {k: v for k, v in changes.items() if k in ("category", "priority", "team")}
        sets = ", ".join(f"{k} = ?" for k in allowed)
        with self.conn:
            self.conn.execute(
                f"UPDATE tickets SET status = ?, final_reply = ?, reviewed_at = ?{', ' + sets if sets else ''} WHERE id = ?",
                (status, reply, datetime.now(timezone.utc).isoformat(), *allowed.values(), ticket_id),
            )

    def all(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM tickets ORDER BY due_at").fetchall()
        return [dict(r) | {"reasons": json.loads(r["reasons"])} for r in rows]

    def get(self, ticket_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(r) | {"reasons": json.loads(r["reasons"])} if r else None

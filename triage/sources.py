"""Turn the formats tickets actually arrive in into Ticket objects."""
import csv
import email
import email.policy
import hashlib
import json
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from .models import Ticket
from .pipeline import TZ


def from_csv(path: Path) -> list[Ticket]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [Ticket(**{k: v for k, v in row.items() if v not in (None, "")}) for row in csv.DictReader(fh)]


def from_json(path: Path) -> list[Ticket]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Ticket(**row) for row in (data if isinstance(data, list) else data["tickets"])]


def from_eml(raw: bytes) -> Ticket:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    part = msg.get_body(preferencelist=("plain", "html"))
    body = part.get_content() if part else ""
    name, addr = parseaddr(msg.get("From", ""))
    msg_id = msg.get("Message-ID") or hashlib.sha1(raw).hexdigest()
    created = parsedate_to_datetime(msg["Date"]) if msg.get("Date") else None
    return Ticket(id=f"EM-{hashlib.sha1(msg_id.encode()).hexdigest()[:8]}", subject=msg.get("Subject", ""),
                  body=_strip_quoted(body) or "(empty)", customer=name or None, email=addr or None,
                  channel="email", created_at=created)


def from_zendesk(payload: dict) -> Ticket:
    """Zendesk webhook (trigger with a JSON body built from ticket placeholders)."""
    t = payload.get("ticket", payload)
    created = t.get("created_at")
    return Ticket(
        id=f"ZD-{t['id']}",
        subject=t.get("subject") or t.get("title", ""),
        body=t.get("description") or t.get("latest_comment") or "",
        customer=(t.get("requester") or {}).get("name"),
        email=(t.get("requester") or {}).get("email"),
        channel=t.get("via", "zendesk"),
        created_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
    )


def shift_to_now(tickets: list[Ticket]) -> list[Ticket]:
    """Move demo tickets in time so the newest one was created just now (keeps SLA timers meaningful).
    Naive timestamps are treated as Riyadh time, same as the pipeline does."""
    aware = [t.model_copy(update={"created_at": t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=TZ)})
             if t.created_at else t for t in tickets]
    dated = [t.created_at for t in aware if t.created_at]
    if not dated:
        return tickets
    delta = datetime.now(TZ).replace(microsecond=0) - max(dated)
    return [t.model_copy(update={"created_at": t.created_at + delta}) if t.created_at else t for t in aware]


def _strip_quoted(body: str) -> str:
    """Drop the quoted previous message from replies ("On Tue, X wrote:" / lines starting with >)."""
    out = []
    for line in body.splitlines():
        if line.startswith(">") or (line.startswith("On ") and line.rstrip().endswith("wrote:")):
            break
        out.append(line)
    return "\n".join(out).strip()

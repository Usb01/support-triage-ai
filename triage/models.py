from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["billing", "technical", "account", "security", "shipping", "feature_request", "general"]
Priority = Literal["low", "normal", "high", "urgent"]
Sentiment = Literal["negative", "neutral", "positive"]

CATEGORIES: tuple[str, ...] = Category.__args__
PRIORITIES: tuple[str, ...] = Priority.__args__


class Ticket(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    subject: str = Field(default="", max_length=300)
    body: str = Field(min_length=1, max_length=10_000)
    customer: str | None = None
    email: str | None = None
    channel: str = "email"
    created_at: datetime | None = None

    @property
    def text(self) -> str:
        return f"{self.subject}\n{self.body}".strip()


class Triage(BaseModel):
    """What the classifier must return. The LLM output is validated against this."""
    category: Category
    priority: Priority
    sentiment: Sentiment
    language: Literal["en", "ar", "other"]
    summary: str = Field(min_length=1, max_length=400)
    draft_reply: str = Field(min_length=1, max_length=3000)
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list, max_length=8)

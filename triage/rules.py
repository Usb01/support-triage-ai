"""Keyword classifier. Used as the default (no API key needed) and as the
fallback whenever the LLM call fails or returns something invalid."""
import re

from .models import Ticket, Triage

ARABIC = re.compile(r"[؀-ۿ]")

CATEGORY_WORDS = {
    "billing": ["invoice", "refund", "charge", "charged", "payment", "billing", "receipt", "subscription", "vat", "pricing", "plan",
                "فاتورة", "استرداد", "دفع"],
    "technical": ["error", "crash", "bug", "not working", "doesn't work", "broken", "outage", "down", "slow",
                  "500", "api", "timeout", "integration", "خطأ", "عطل"],
    "account": ["login", "log in", "password", "2fa", "locked", "account", "sign in", "reset", "email change",
                "كلمة المرور", "حساب"],
    "security": ["hacked", "security", "breach", "phishing", "suspicious login", "accessed my account",
                 "unauthorized", "someone else logged", "اختراق"],
    "shipping": ["delivery", "shipment", "tracking", "courier", "package", "parcel", "arrived", "delayed",
                 "توصيل", "شحنة"],
    "feature_request": ["feature", "would be great", "please add", "suggestion", "wish", "could you add", "roadmap"],
}

URGENT = ["outage", "down for everyone", "security", "hacked", "data breach", "cannot access", "can't access",
          "all users", "production", "urgent", "asap", "عاجل"]
HIGH = ["charged twice", "double charged", "refund", "locked out", "deadline", "today", "still waiting",
        "second time", "third time", "lost", "مرتين", "استرداد"]
NEGATIVE = ["angry", "terrible", "worst", "unacceptable", "disappointed", "frustrated", "ridiculous", "cancel",
            "still", "again", "!!!", "never"]
POSITIVE = ["thanks", "thank you", "great", "love", "appreciate", "شكرا"]

REPLIES = {
    "billing": "Thanks for reaching out about your billing question. I'm checking the invoice and payment records "
               "on your account now and will confirm the details shortly.",
    "technical": "Thanks for reporting this. Could you tell me roughly when it started and share a screenshot of "
                 "the error? I've also passed it to our technical team.",
    "account": "For your security we can't change account access over email. Please use 'Forgot password' on the "
               "sign-in page. If that doesn't work, reply here and we'll verify your identity.",
    "security": "Thanks for flagging this – I've escalated it to our security team as a priority. In the meantime, "
                "please reset your password and turn on two-factor authentication. We'll review the recent sign-ins "
                "on your account and update you as soon as we know more.",
    "shipping": "Thanks for getting in touch. Could you share your order or tracking number? I'll check the latest "
                "status with the courier.",
    "feature_request": "Thanks for the suggestion! I've logged it with our product team. We can't promise a date, "
                       "but requests like this do shape the roadmap.",
    "general": "Thanks for your message. I'm looking into this and will get back to you shortly.",
}


def _hits(text: str, words: list[str]) -> list[str]:
    found = []
    for w in words:
        if ARABIC.search(w):
            # Arabic attaches prefixes like ال / و to words, so match anywhere
            hit = w in text
        else:
            # allow short suffixes: crash -> crashes, charge -> charged
            hit = re.search(rf"(?<!\w){re.escape(w)}\w{{0,2}}(?!\w)", text)
        if hit:
            found.append(w)
    return found


def classify(ticket: Ticket) -> Triage:
    text = ticket.text.lower()
    reasons = []

    scores = {cat: _hits(text, words) for cat, words in CATEGORY_WORDS.items()}
    # ties go to the more serious category
    order = ["security", "technical", "billing", "account", "shipping", "feature_request"]
    best = max(order, key=lambda c: (len(scores[c]), -order.index(c)))
    if scores[best]:
        category = best
        reasons.append(f"{category}: {', '.join(scores[best][:3])}")
        runner_up = sorted((len(v) for v in scores.values()), reverse=True)[1]
        confidence = 0.55 if runner_up == len(scores[best]) else 0.75
    else:
        category, confidence = "general", 0.4

    if u := _hits(text, URGENT):
        priority = "urgent"
        reasons.append(f"urgent: {', '.join(u[:2])}")
    elif h := _hits(text, HIGH):
        priority = "high"
        reasons.append(f"high: {', '.join(h[:2])}")
    elif category == "feature_request":
        priority = "low"
    else:
        priority = "normal"

    neg, pos = _hits(text, NEGATIVE), _hits(text, POSITIVE)
    sentiment = "negative" if len(neg) > len(pos) else "positive" if pos else "neutral"
    if sentiment == "negative" and priority == "normal":
        priority = "high"
        reasons.append("negative sentiment bumped priority")

    language = "ar" if ARABIC.search(ticket.text) else "en"
    first = re.split(r"(?<=[.!?])\s", ticket.body.strip())[0]
    summary = (ticket.subject + " – " if ticket.subject else "") + first
    name = (ticket.customer or "").split(" ")[0]

    return Triage(
        category=category,
        priority=priority,
        sentiment=sentiment,
        language=language,
        summary=summary[:400],
        draft_reply=f"Hi {name or 'there'},\n\n{REPLIES[category]}\n\nBest regards,\nSupport team",
        confidence=confidence,
        reasons=reasons,
    )

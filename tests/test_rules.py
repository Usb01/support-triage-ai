import pytest

from triage.models import Ticket
from triage.rules import classify


def t(body, subject=""):
    return classify(Ticket(id="x", subject=subject, body=body, customer="Sara Malik"))


@pytest.mark.parametrize("body,category", [
    ("Please send me a copy of the invoice", "billing"),
    ("The API returns a 500 error since this morning", "technical"),
    ("I can't log in, my password reset didn't work", "account"),
    ("Someone accessed my account, I think it was hacked", "security"),
    ("My parcel tracking hasn't updated in 3 days", "shipping"),
    ("Would be great if you could add dark mode", "feature_request"),
    ("Hello, quick question about your company", "general"),
])
def test_categories(body, category):
    assert t(body).category == category


def test_suffixes_match():
    assert t("The app crashes on Android").category == "technical"


def test_accountant_is_not_account():
    assert t("Our accountant needs the invoice").category == "billing"


def test_outage_is_urgent():
    assert t("The dashboard is down for everyone in production").priority == "urgent"


def test_double_charge_is_high():
    assert t("I was charged twice this month").priority == "high"


def test_feature_requests_are_low():
    assert t("Suggestion: please add an Excel export").priority == "low"


def test_angry_customer_bumped_to_high():
    r = t("Where is my delivery? This is unacceptable and ridiculous")
    assert r.sentiment == "negative" and r.priority == "high"


def test_arabic_detected_and_classified():
    r = t("تم خصم المبلغ مرتين في الفاتورة، أرجو الاسترداد")
    assert r.language == "ar" and r.category == "billing" and r.priority == "high"


def test_draft_uses_first_name_and_no_promises():
    r = t("I want a refund for last month")
    assert r.draft_reply.startswith("Hi Sara,")
    assert "will refund" not in r.draft_reply.lower()


def test_low_confidence_when_nothing_matches():
    assert t("hello").confidence < 0.5

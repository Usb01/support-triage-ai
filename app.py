"""Review queue for triaged tickets.

    streamlit run app.py
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from triage import sources
from triage.pipeline import TEAMS, Pipeline
from triage.models import CATEGORIES, PRIORITIES
from triage.store import Store

DB = os.getenv("TRIAGE_DB", "triage.db")
SAMPLE = Path(__file__).parent / "data" / "sample_tickets.csv"
PRIORITY_ICON = {"urgent": "🔴", "high": "🟠", "normal": "🔵", "low": "⚪"}

st.set_page_config(page_title="Support Triage", page_icon="🎧", layout="wide")
store = Store(DB)


def load_sample():
    pipe = Pipeline()
    for t in sources.shift_to_now(sources.from_csv(SAMPLE)):
        store.save(pipe.run(t))


rows = store.all()
with st.sidebar:
    st.header("Support Triage")
    st.caption(f"Engine: **{os.getenv('TRIAGE_ENGINE', 'rules')}** · DB: `{DB}`")
    if not rows and st.button("Load 30 sample tickets", type="primary"):
        load_sample()
        st.rerun()
    up = st.file_uploader("Import tickets (CSV / JSON / .eml)", type=["csv", "json", "eml"])
    if up is not None and st.button("Import"):
        tmp = Path(st.session_state.get("tmpdir", "/tmp")) / up.name
        tmp.write_bytes(up.getvalue())
        tickets = ([sources.from_eml(up.getvalue())] if up.name.endswith(".eml")
                   else sources.from_csv(tmp) if up.name.endswith(".csv") else sources.from_json(tmp))
        pipe = Pipeline()
        added = sum(store.save(pipe.run(t)) for t in tickets)
        st.success(f"Imported {added} new ticket(s)")
        st.rerun()

    st.divider()
    f_status = st.multiselect("Status", ["open", "approved", "closed"], default=["open"])
    f_team = st.multiselect("Team", sorted(set(TEAMS.values())))
    f_review = st.toggle("Only flagged for review", value=False)

if not rows:
    st.info("No tickets yet. Load the sample set from the sidebar, or run `python -m triage import <file>`.")
    st.stop()

df = pd.DataFrame(rows)
df["due_at"] = pd.to_datetime(df["due_at"], utc=True, format="ISO8601")
now = pd.Timestamp(datetime.now(timezone.utc))

# --- KPIs -----------------------------------------------------------------
open_df = df[df.status == "open"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Open", len(open_df))
c2.metric("Urgent", int((open_df.priority == "urgent").sum()))
c3.metric("Flagged for review", int(open_df.needs_review.sum()))
c4.metric("Past SLA", int((open_df.due_at < now).sum()))
c5.metric("Approved", int((df.status == "approved").sum()))

left, right = st.columns([3, 2])
with left:
    st.subheader("By category")
    st.bar_chart(df.category.value_counts(), horizontal=True, height=220)
with right:
    st.subheader("By priority")
    counts = df.priority.value_counts().reindex(list(PRIORITIES)).fillna(0)
    counts.index = [f"{PRIORITY_ICON[p]} {p}" for p in counts.index]
    st.bar_chart(counts, height=220)

# --- queue ----------------------------------------------------------------
view = df[df.status.isin(f_status)] if f_status else df
if f_team:
    view = view[view.team.isin(f_team)]
if f_review:
    view = view[view.needs_review == 1]
prio_rank = {p: i for i, p in enumerate(reversed(PRIORITIES))}
view = view.assign(_p=view.priority.map(prio_rank)).sort_values(["_p", "due_at"])

st.subheader(f"Queue ({len(view)})")
table = pd.DataFrame({
    "": view.priority.map(PRIORITY_ICON),
    "Ticket": view.id,
    "Subject": view.subject,
    "Category": view.category,
    "Team": view.team,
    "Due": view.due_at.dt.tz_convert("Asia/Riyadh").dt.strftime("%a %d %b %H:%M"),
    "Review": view.needs_review.map({1: "⚑", 0: ""}),
    "Lang": view.language,
})
picked = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun",
                      selection_mode="single-row", height=320)

sel = picked.selection.rows if picked and picked.selection else []
ticket_id = view.iloc[sel[0]].id if sel else (view.iloc[0].id if len(view) else None)
if ticket_id is None:
    st.stop()

t = store.get(ticket_id)
st.divider()
a, b = st.columns([3, 2])
with a:
    st.markdown(f"#### {PRIORITY_ICON[t['priority']]} {t['subject']}  \n"
                f"<span style='color:#888'>{t['id']} · {t['customer']} &lt;{t['email']}&gt; · {t['channel']}</span>",
                unsafe_allow_html=True)
    st.text(t["body"])
    reply = st.text_area("Draft reply (edit before approving)", t["final_reply"] or t["draft_reply"], height=180)
with b:
    st.markdown("**Triage**")
    category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(t["category"]))
    priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(t["priority"]))
    st.markdown(f"Team: **{TEAMS[category]}**  \nSentiment: {t['sentiment']}  \n"
                f"Confidence: {t['confidence']:.0%} ({t['engine']})  \nWhy: {'; '.join(t['reasons']) or '–'}")
    if t["fallback"]:
        st.warning(f"LLM failed, rules used: {t['fallback']}")
    c_ok, c_close = st.columns(2)
    if c_ok.button("Approve reply", type="primary", width="stretch"):
        store.review(t["id"], reply, "approved", category=category, priority=priority, team=TEAMS[category])
        st.toast(f"{t['id']} approved")
        st.rerun()
    if c_close.button("Close without reply", width="stretch"):
        store.review(t["id"], "", "closed")
        st.rerun()

# app.py
import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

# Import the wrapper — ai_service should implement:
#   generate_ai_feedback(review, rating) -> dict
#   is_real_client_available() -> bool
from ai_service import generate_ai_feedback, is_real_client_available

# ---------------------- CONFIG / STYLE ----------------------
st.set_page_config(page_title="AI Feedback — Public", page_icon="🤖", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #f6f7fb;
        --card: #ffffff;
        --muted: #6b7280;
        --accent: #0f172a;
    }
    .stApp { background-color: var(--bg); }
    .card { background: var(--card); padding: 18px; border-radius: 12px; box-shadow: 0 6px 20px rgba(12,24,48,0.06); }
    .brand { font-size:22px; font-weight:700; color:var(--accent); margin-bottom:4px; }
    .muted { color: var(--muted); font-size:13px; }
    .small { font-size:13px; color:var(--muted); }
    .ai-response { background:#fbfdff; padding:12px; border-radius:8px; }
    .status-live { color: #0f9d58; font-weight:600; }
    .status-stub { color: #ff8a00; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------- STORAGE (SQLite) ----------------------
DB_PATH = "feedback.db"
TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rating INTEGER NOT NULL,
    review TEXT NOT NULL,
    summary TEXT,
    actions TEXT,
    timestamp TEXT NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(TABLE_SCHEMA)
    conn.commit()
    conn.close()


def insert_feedback_sql(record: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (rating, review, summary, actions, timestamp) VALUES (?, ?, ?, ?, ?)",
        (record["rating"], record["review"], record.get("summary", ""), record.get("actions", ""), record["timestamp"]),
    )
    conn.commit()
    conn.close()


def fetch_recent_sql(limit=5):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT rating, review, summary, actions, timestamp FROM feedback ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"rating": r[0], "review": r[1], "summary": r[2], "actions": r[3], "timestamp": r[4]} for r in rows
    ]


# init DB
init_db()

# initialize session_state keys we'll use
if "ai_summary" not in st.session_state:
    st.session_state.ai_summary = ""
if "ai_actions" not in st.session_state:
    st.session_state.ai_actions = ""
if "submit_error" not in st.session_state:
    st.session_state.submit_error = ""
# default values for form widgets (so they exist in session_state)
if "rating" not in st.session_state:
    st.session_state.rating = 5
if "review" not in st.session_state:
    st.session_state.review = ""

# ---------------------- UI (top header + status) ----------------------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("<div class='brand'>🤖 AI Feedback — Public</div>", unsafe_allow_html=True)
st.markdown("<div class='muted'>Share quick feedback — we'll summarize it with AI and surface suggested actions.</div>", unsafe_allow_html=True)

# show whether real Google client is available or the app is running in stub mode
try:
    live = is_real_client_available()
except Exception:
    live = False

if live:
    st.markdown("<div class='small status-live'>Live LLM: Google Generative API available ✅</div>", unsafe_allow_html=True)
else:
    st.markdown(
        "<div class='small status-stub'>LLM: running in <strong>stub</strong> mode — add GOOGLE_API_KEY and install google-generative-ai to enable live responses.</div>",
        unsafe_allow_html=True,
    )

st.markdown("<hr/>", unsafe_allow_html=True)

MAX_CHARS = 600

# ---------------------- Submission callback ----------------------
def handle_submit():
    """
    Callback attached to the form submit button.
    Reads values from session_state, calls the AI wrapper, persists feedback and updates UI state.
    """
    review_text = st.session_state.get("review", "").strip()
    rating_val = int(st.session_state.get("rating", 5))

    # validation
    if not review_text:
        st.session_state["submit_error"] = "Please write a short review before submitting."
        return
    if len(review_text) > MAX_CHARS:
        st.session_state["submit_error"] = f"Please shorten your review to under {MAX_CHARS} characters."
        return

    st.session_state["submit_error"] = ""

    # call LLM (wrapped)
    try:
        ai = generate_ai_feedback(review_text, rating_val)
    except Exception as e:
        st.session_state["submit_error"] = f"AI service failed: {e}"
        ai = {"response": "", "summary": "", "actions": ""}

    record = {
        "rating": rating_val,
        "review": review_text,
        "summary": ai.get("summary", "") if isinstance(ai, dict) else "",
        "actions": ai.get("actions", "") if isinstance(ai, dict) else "",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    # persist to SQLite
    try:
        insert_feedback_sql(record)
    except Exception as e:
        st.error(f"Failed to save feedback: {e}")
        return

    # update session_state for UI
    st.session_state.ai_summary = record["summary"]
    st.session_state.ai_actions = record["actions"]

    # safely clear the review field (allowed inside callback)
    st.session_state.review = ""

    # optional: set a flag that submission succeeded
    st.session_state.last_submitted_ts = record["timestamp"]
    return


# ---------------------- UI Form ----------------------
with st.form("feedback_form"):
    cols = st.columns([3, 1])
    with cols[0]:
        # radio widget bound to st.session_state["rating"]
        star_labels = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}
        st.radio("Rating", options=[5, 4, 3, 2, 1], index=0, format_func=lambda x: star_labels[x], key="rating", horizontal=True)

        # text_area bound to st.session_state["review"]
        st.text_area("Write your review", height=160, placeholder="1–3 sentences: what happened, what you liked, what broke...", key="review")

        # char counter (reads session_state.review)
        chars = len(st.session_state.get("review", "") or "")
        st.markdown(f"<div class='small muted'>{chars}/{MAX_CHARS} characters</div>", unsafe_allow_html=True)
        if chars > MAX_CHARS:
            st.error("Please shorten your review to under 600 characters.")

    with cols[1]:
        st.checkbox("Submit anonymously", value=False, key="submit_anon")
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        # wire submit button to handle_submit callback
        st.form_submit_button("Submit feedback", on_click=handle_submit)

# If callback set an error, display it
if st.session_state.get("submit_error"):
    st.error(st.session_state.get("submit_error"))

# Show AI response if available (set by callback)
if st.session_state.get("ai_summary") or st.session_state.get("ai_actions"):
    st.success("Thanks — your feedback was recorded!")
    st.markdown("<div class='ai-response'>", unsafe_allow_html=True)
    st.subheader("AI-generated summary")
    st.write(st.session_state.get("ai_summary", ""))
    st.markdown("**Suggested actions**")
    st.write(st.session_state.get("ai_actions", ""))
    # optionally show last submission time
    if st.session_state.get("last_submitted_ts"):
        st.markdown(f"<div class='small muted'>Submitted at {st.session_state.get('last_submitted_ts')} (UTC)</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# recent submissions preview
st.markdown("<hr/>", unsafe_allow_html=True)
st.subheader("Recent submissions (preview)")
try:
    recent = fetch_recent_sql(limit=5)
except Exception:
    recent = []

if recent:
    for rec in recent:
        ts = rec.get("timestamp", "")
        rating_badge = f"{int(rec.get('rating', 0))}★"
        st.markdown(f"**{ts}** — {rating_badge}")
        st.markdown(f"{rec.get('review','')}")
        if rec.get("summary"):
            st.markdown(f"*AI summary:* {rec.get('summary')}")
        if rec.get("actions"):
            st.markdown(f"*AI actions:* {rec.get('actions')}")
        st.markdown("---")
else:
    st.info("No submissions yet. Be the first to add feedback!")

st.markdown("</div>", unsafe_allow_html=True)

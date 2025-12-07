# app.py
import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from ai_service import generate_ai_feedback, is_real_client_available

# -------------------- Page config --------------------
st.set_page_config(page_title="AI Feedback — Public", page_icon="🤖", layout="wide")

# -------------------- Styling (CSS) --------------------
st.markdown(
    """
    <style>
    :root{
      --bg: #f6f7fb;
      --card: #ffffff;
      --muted: #6b7280;
      --accent: #0f172a;
      --accent-2: #0f9d58;
      --danger: #ff6b6b;
      --glass: rgba(255,255,255,0.6);
    }
    html, body, .main {
      background: var(--bg);
    }
    /* page container */
    .page-header {
      padding: 28px 18px;
      border-radius: 12px;
      margin-bottom: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.7), rgba(255,255,255,0.5));
      box-shadow: 0 6px 20px rgba(12,24,48,0.04);
    }
    .brand {
      display:flex; gap:12px; align-items:center;
      font-size:28px; font-weight:700; color:var(--accent);
    }
    .sub { margin-top:6px; color:var(--muted); font-size:14px; }

    /* card */
    .card {
      background: var(--card);
      padding: 18px;
      border-radius: 12px;
      box-shadow: 0 6px 20px rgba(12,24,48,0.04);
      margin-bottom: 18px;
    }

    /* form layout */
    .rating-row { display:flex; align-items:center; gap:14px; margin-bottom:8px; }
    .stars { font-size: 26px; letter-spacing:6px; color:#f3c623; }
    .star-muted { color:#e6e6e6; }

    /* textarea look */
    textarea[role="textbox"], .stTextArea>div>div>textarea {
      background: #0f1721;
      color: #f5f7fa;
      border-radius: 10px;
      padding: 18px;
      border: 1px solid rgba(0,0,0,0.06);
      min-height: 160px;
    }

    /* nice button */
    .stButton>button {
      background: linear-gradient(180deg,#0f172a,#0c1420);
      color: white;
      padding: 10px 22px;
      border-radius: 10px;
      box-shadow: 0 6px 18px rgba(12,24,48,0.12);
      border: none;
    }
    .stButton>button:hover { transform: translateY(-1px); }

    /* success box */
    .success-box {
      background: linear-gradient(90deg,#e6f9ec,#dff3e6);
      border-left: 4px solid var(--accent-2);
      padding: 12px;
      border-radius: 8px;
    }

    /* small muted */
    .muted { color: var(--muted); font-size:13px; }

    /* responsive adjustments */
    @media (max-width: 900px) {
      .brand { font-size:22px; }
      .stars { font-size:22px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- Storage helpers (same as before) --------------------
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
    return sqlite3.connect(DB_PATH, check_same_thread=False)


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
    return [{"rating": r[0], "review": r[1], "summary": r[2], "actions": r[3], "timestamp": r[4]} for r in rows]


init_db()

# -------------------- session defaults --------------------
if "ai_summary" not in st.session_state:
    st.session_state.ai_summary = ""
if "ai_actions" not in st.session_state:
    st.session_state.ai_actions = ""
if "submit_error" not in st.session_state:
    st.session_state.submit_error = ""
if "rating" not in st.session_state:
    st.session_state.rating = 5
if "review" not in st.session_state:
    st.session_state.review = ""

# -------------------- Top header --------------------
st.markdown('<div class="page-header">', unsafe_allow_html=True)
st.markdown('<div class="brand">🤖 AI Feedback — Public</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Share quick feedback — we summarize it with AI and surface suggested actions.</div>', unsafe_allow_html=True)

# show live/stub
try:
    live = is_real_client_available()
except Exception:
    live = False

if live:
    st.markdown('<div style="margin-top:8px" class="muted"><strong style="color:#0f9d58">Live LLM:</strong> Google Generative API available ✅</div>', unsafe_allow_html=True)
else:
    st.markdown('<div style="margin-top:8px" class="muted"><strong style="color:#ff8a00">LLM:</strong> running in stub mode — add GOOGLE_API_KEY and install google-generative-ai to enable live responses.</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.write("")  # spacing

# -------------------- Feedback card/form --------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="display:flex; justify-content:space-between; align-items:center;">', unsafe_allow_html=True)
    st.markdown('<div><h3 style="margin:0">Submit your feedback</h3><div class="muted">Short, clear feedback helps us act faster.</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    MAX_CHARS = 600

    # form (use Streamlit form to group)
    with st.form("feedback_form"):
        cols = st.columns([3, 1], gap="large")
        with cols[0]:
            # star rating: visually bigger
            star_labels = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}
            st.markdown('<div class="rating-row"><div style="font-weight:600; color:#111">Rating</div></div>', unsafe_allow_html=True)
            st.radio("", options=[5, 4, 3, 2, 1], index=0, format_func=lambda x: star_labels[x], key="rating", horizontal=True)
            st.text_area("Write your review", height=180, placeholder="1–3 sentences: what happened, what you liked, what broke...", key="review")
            chars = len(st.session_state.get("review", "") or "")
            st.markdown(f"<div class='muted'>{chars}/{MAX_CHARS} characters</div>", unsafe_allow_html=True)
            if chars > MAX_CHARS:
                st.error("Please shorten your review to under 600 characters.")

        with cols[1]:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.checkbox("Submit anonymously", value=False, key="submit_anon")
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.form_submit_button("Submit feedback", on_click=lambda: _handle_submit := None)  # placeholder to render button

        # capture submit with explicit button below (keeps styling consistent)
        submitted = st.form_submit_button("Submit feedback")
        # Note: we intentionally use the same callback pattern below for clarity
        if submitted:
            # validate
            review_text = st.session_state.get("review", "").strip()
            rating_val = int(st.session_state.get("rating", 5))
            if not review_text:
                st.session_state.submit_error = "Please write a short review before submitting."
            elif len(review_text) > MAX_CHARS:
                st.session_state.submit_error = f"Please shorten your review to under {MAX_CHARS} characters."
            else:
                st.session_state.submit_error = ""
                # call the AI service
                try:
                    ai = generate_ai_feedback(review_text, rating_val)
                except Exception as e:
                    st.session_state.submit_error = f"AI service failed: {e}"
                    ai = {"response": "", "summary": "", "actions": ""}

                record = {
                    "rating": rating_val,
                    "review": review_text,
                    "summary": ai.get("summary", "") if isinstance(ai, dict) else "",
                    "actions": ai.get("actions", "") if isinstance(ai, dict) else "",
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
                try:
                    insert_feedback_sql(record)
                except Exception as e:
                    st.error(f"Failed to save feedback: {e}")
                else:
                    st.session_state.ai_summary = record["summary"]
                    st.session_state.ai_actions = record["actions"]
                    st.session_state.last_submitted_ts = record["timestamp"]
                    st.session_state.review = ""

    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Feedback result / AI response --------------------
if st.session_state.get("submit_error"):
    st.error(st.session_state.get("submit_error"))

if st.session_state.get("ai_summary") or st.session_state.get("ai_actions"):
    st.markdown('<div class="card success-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:600; color:#0f592f'>Thanks — your feedback was recorded!</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:8px'><strong>AI-generated summary</strong></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-top:6px'>{st.session_state.get('ai_summary','')}</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:8px'><strong>Suggested actions</strong></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-top:6px'>{st.session_state.get('ai_actions','')}</div>", unsafe_allow_html=True)
    if st.session_state.get("last_submitted_ts"):
        st.markdown(f"<div class='muted' style='margin-top:8px'>Submitted at {st.session_state.get('last_submitted_ts')} (UTC)</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------- Recent submissions --------------------
st.write("")
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("<h4 style='margin:0 0 8px 0'>Recent submissions</h4>", unsafe_allow_html=True)
recent = fetch_recent_sql(limit=8)
if recent:
    for r in recent:
        ts = r.get("timestamp", "")
        rating_badge = f"{int(r.get('rating',0))}★"
        st.markdown(f"**{ts}** — {rating_badge}")
        st.markdown(r.get("review",""))
        if r.get("summary"):
            st.markdown(f"*AI summary:* {r.get('summary')}")
        if r.get("actions"):
            st.markdown(f"*AI actions:* {r.get('actions')}")
        st.markdown("---")
else:
    st.info("No submissions yet. Be the first to add feedback!")
st.markdown("</div>", unsafe_allow_html=True)

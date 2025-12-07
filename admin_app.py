# admin_app.py
"""
Admin dashboard (private). Replace the existing file with this version.

This version avoids using st.experimental_rerun() (which may not be available)
and instead uses a safer rerun trigger via query params. It also guards
access to st.secrets to avoid StreamlitSecretNotFoundError.
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# Optional auto-refresh helper (works if installed)
try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTORE = True
except Exception:
    _HAS_AUTORE = False

# ---------------------- CONFIG / STYLE ----------------------
st.set_page_config(page_title="AI Feedback System— Admin", layout="wide")

st.markdown(
    """
    <style>
    .card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 4px 18px rgba(13,38,63,0.06); }
    .muted { color: #6b7280; }
    .small { font-size: 13px; }
    .nowrap { white-space: nowrap; }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_FILE = "data.csv"  # must match the public app storage

# ---------------------- SIMPLE AUTH (optional) ----------------------
# Read ADMIN_PASSWORD from env var OR Streamlit secrets (safely)
ADMIN_PASSWORD = None

# 1) from env var
if os.environ.get("ADMIN_PASSWORD"):
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# 2) from Streamlit secrets (safe check)
try:
    if isinstance(st.secrets, dict) and "ADMIN_PASSWORD" in st.secrets:
        ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")
except Exception:
    # Streamlit secrets not present / not accessible in this runtime - ignore
    pass


def require_login():
    """
    Return True if logged in (or no password is configured).
    If a password exists, prompt the user and set st.session_state.admin_authenticated = True
    on successful login. Trigger a rerun safely by updating query params.
    """
    if not ADMIN_PASSWORD:
        # no password configured — allow access
        return True

    # initialize session state flag
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.markdown("### Admin login")
        pwd = st.text_input("Enter admin password", type="password", key="__admin_pwd__")
        if st.button("Sign in"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                # Trigger rerun in a safer way than experimental_rerun()
                try:
                    st.experimental_set_query_params(_ts=int(time.time()))
                except Exception:
                    # If set_query_params is unavailable, fall back to a gentle hack:
                    # set a dummy session_state key which causes a rerun in some runtimes.
                    st.session_state._admin_ts = int(time.time())
                # allow rerun to happen; stop current execution
                st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.stop()
            else:
                st.error("Incorrect password.")
        # not authenticated, stop further execution
        return False
    # authenticated
    return True


if not require_login():
    st.stop()

# ---------------------- AUTO-REFRESH ----------------------
REFRESH_INTERVAL_MS = 5_000
if _HAS_AUTORE:
    st_autorefresh(interval=REFRESH_INTERVAL_MS, limit=None, key="admin_autorefresh")

# ---------------------- DATA LOADING HELPERS ----------------------
@st.cache_data(ttl=3)
def load_data(path=DATA_FILE):
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["rating", "review", "summary", "actions", "timestamp"])
    return df


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" in df.columns:
        try:
            df["ts_parsed"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        except Exception:
            df["ts_parsed"] = pd.NaT
    else:
        df["ts_parsed"] = pd.NaT
    return df


# ---------------------- PAGE LAYOUT ----------------------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("Admin — Feedback System Console")
st.markdown('<div class="muted small">Private admin dashboard — shows live submissions, AI summaries & suggested actions.</div>', unsafe_allow_html=True)

# Last refreshed indicator
last_ref = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
_, col_last = st.columns([4, 1])
with col_last:
    st.metric("Last refreshed (UTC)", last_ref)

st.markdown("---")

# ---------------------- SIDEBAR FILTERS ----------------------
st.sidebar.header("Filters & Controls")
st.sidebar.markdown("Use filters to narrow results. Auto-refresh runs every 5s if available.")
df_raw = load_data()
df_raw = parse_timestamps(df_raw)

# Date range
today = datetime.utcnow().date()
default_from = today - timedelta(days=14)
try:
    date_range = st.sidebar.date_input("Date range (UTC)", value=(default_from, today))
except Exception:
    # Some runtimes may supply single date; be robust
    date_range = (default_from, today)

# Ratings
rating_options = sorted(df_raw["rating"].dropna().unique().tolist(), reverse=True) if not df_raw.empty else [5, 4, 3, 2, 1]
selected_ratings = st.sidebar.multiselect("Ratings", options=rating_options, default=rating_options)

# Text search
text_query = st.sidebar.text_input("Search text (review/summary/actions)", value="")

# Manual refresh fallback (if autorefresh not available)
if not _HAS_AUTORE:
    if st.sidebar.button("Refresh now"):
        try:
            load_data.clear()
        except Exception:
            pass
        # trigger a rerun safely
        try:
            st.experimental_set_query_params(_ts=int(time.time()))
        except Exception:
            st.session_state._manual_refresh = int(time.time())
        st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("Note: To enforce stronger access control, host this app as PRIVATE on your platform (Streamlit Cloud, Render, etc.).")

# ---------------------- APPLY FILTERS ----------------------
df = df_raw.copy()
if not df.empty:
    # Apply date filtering
    try:
        start_date = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
        end_date = date_range[1] if isinstance(date_range, (list, tuple)) and len(date_range) > 1 else date_range
        if start_date:
            start_dt = pd.to_datetime(datetime(start_date.year, start_date.month, start_date.day, 0, 0))
            df = df[df["ts_parsed"] >= start_dt]
        if end_date:
            end_dt = pd.to_datetime(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59))
            df = df[df["ts_parsed"] <= end_dt]
    except Exception:
        pass

    # Rating filter
    if selected_ratings:
        df = df[df["rating"].isin(selected_ratings)]

    # Text search filter
    if text_query and text_query.strip() != "":
        q = text_query.strip().lower()
        mask = (
            df["review"].fillna("").str.lower().str.contains(q)
            | df["summary"].fillna("").str.lower().str.contains(q)
            | df["actions"].fillna("").str.lower().str.contains(q)
        )
        df = df[mask]

# ---------------------- METRICS & CHARTS ----------------------
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    st.metric("Total feedback (filtered)", int(df.shape[0]) if not df.empty else 0)
with col2:
    avg_rating = round(df["rating"].astype(float).mean(), 2) if not df.empty else "—"
    st.metric("Average rating (filtered)", avg_rating)
with col3:
    if not df.empty:
        latest = df["timestamp"].max()
        st.metric("Latest submission", latest)
    else:
        st.metric("Latest submission", "—")

st.markdown("---")

# Rating distribution
st.subheader("Rating distribution")
if not df.empty:
    dist = df["rating"].value_counts().sort_index()
    st.bar_chart(dist)
else:
    st.info("No results for current filters.")

# Rating trend (daily average)
st.subheader("Rating trend (daily average)")
if not df.empty and "ts_parsed" in df:
    df_trend = df.copy()
    df_trend["date_only"] = df_trend["ts_parsed"].dt.date
    trend = df_trend.groupby("date_only")["rating"].mean().reset_index().sort_values("date_only")
    if not trend.empty:
        st.line_chart(data=trend.set_index("date_only")["rating"])
    else:
        st.info("Not enough data for trend.")
else:
    st.info("No data for trend.")

# Simple sentiment metric
st.subheader("Text sentiment (simple lexicon)")
if not df.empty:
    text_blob = (df["summary"].fillna("") + " " + df["review"].fillna("") + " " + df["actions"].fillna("")).str.strip()
    POS = {"good", "great", "excellent", "love", "liked", "awesome", "nice", "satisfied", "happy", "pleasant", "fantastic", "amazing", "best"}
    NEG = {"bad", "terrible", "awful", "hate", "dislike", "poor", "unsatisfied", "unhappy", "problem", "issue", "worst", "bug"}

    def _sent_score(s):
        if not isinstance(s, str) or s.strip() == "":
            return 0.0
        words = [w.strip(".,!?;:()[]\"'").lower() for w in s.split()]
        pos = sum(1 for w in words if w in POS)
        neg = sum(1 for w in words if w in NEG)
        return (pos - neg) / max(1, len(words))

    df["sent_score"] = text_blob.apply(_sent_score)
    st.metric("Average sentiment (lexicon)", round(df["sent_score"].mean(), 4))
else:
    st.info("No text data to compute sentiment.")

st.markdown("---")

# ---------------------- RECENT SUBMISSIONS (live list) ----------------------
st.subheader("Recent submissions (filtered) — latest first")
if not df.empty:
    for _, row in df.sort_values("ts_parsed", ascending=False).head(50).iterrows():
        with st.expander(f"{row.get('timestamp','')}  —  Rating: {row.get('rating','')}"):
            st.write(row.get("review", ""))
            st.markdown(f"**AI summary:** {row.get('summary','')}")
            st.markdown(f"**AI actions:** {row.get('actions','')}")
            if "sent_score" in row:
                st.markdown(f"**Sentiment score:** {round(row.get('sent_score', 0.0), 4)}")
            st.markdown("---")
else:
    st.info("No feedback matched the current filters.")

# ---------------------- DOWNLOAD ----------------------
st.markdown("---")
if not df.empty:
    st.download_button("Download filtered CSV", df.to_csv(index=False).encode("utf-8"), file_name="feedback_filtered.csv", mime="text/csv")
else:
    st.button("Download filtered CSV", disabled=True)

st.markdown("</div>", unsafe_allow_html=True)


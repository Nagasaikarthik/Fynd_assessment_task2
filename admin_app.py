# admin_app.py
"""
Enhanced Private Admin Dashboard for AI Feedback System

- Reads from the same data source as the public User app (data.csv).
- Optional simple password protection via ADMIN_PASSWORD env var or Streamlit secrets.
- Optional auto-refresh using `streamlit-autorefresh` (install if you want true auto refresh).
- Filtering, analytics, recent submissions, and CSV download for filtered view.
"""
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# Optional auto-refresh package
try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTORE = True
except Exception:
    _HAS_AUTORE = False

# ---------------------- CONFIG / STYLE ----------------------
st.set_page_config(page_title="AI Feedback — Admin", page_icon="🛠", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #f6f7fb;
        --card: #ffffff;
        --muted: #6b7280;
        --accent: #0f172a;
        --accent-2: #0ea5a3;
    }
    .stApp { background-color: var(--bg); }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:8px; }
    .brand { font-size:20px; font-weight:700; color:var(--accent); display:flex; gap:10px; align-items:center; }
    .subtitle { color:var(--muted); font-size:13px; }
    .card { background: var(--card); padding: 18px; border-radius: 12px; box-shadow: 0 6px 20px rgba(12, 24, 48, 0.06); }
    .kpi { background: linear-gradient(180deg, rgba(255,255,255,0.6), rgba(255,255,255,0.2)); padding:12px; border-radius:10px; }
    .kpi h3 { margin:0; font-size:14px; color:var(--muted); }
    .kpi .value { font-size:20px; font-weight:700; color:var(--accent); margin-top:6px; }
    .small { font-size:13px; color:var(--muted); }
    .rating-badge { display:inline-block; padding:6px 8px; border-radius:8px; color:white; font-weight:700; font-size:12px; }
    .r5 { background:#16a34a; } /* green */
    .r4 { background:#60a5fa; } /* blue */
    .r3 { background:#f59e0b; } /* amber */
    .r2 { background:#f97316; } /* orange */
    .r1 { background:#ef4444; } /* red */
    .muted { color:var(--muted); }
    .compact-expander .streamlit-expanderHeader { padding: 8px 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_FILE = "data.csv"  # must match the public app storage

# ---------------------- SAFE ADMIN PASSWORD LOOKUP ----------------------
ADMIN_PASSWORD = None
if os.environ.get("ADMIN_PASSWORD"):
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
try:
    # safe access to st.secrets (won't crash if none)
    if "ADMIN_PASSWORD" in st.secrets:
        ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    pass


def require_login():
    """Return True if logged in (or no password configured)."""
    if not ADMIN_PASSWORD:
        return True
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    if not st.session_state.admin_authenticated:
        st.markdown("### Admin login")
        pwd = st.text_input("Enter admin password", type="password")
        if st.button("Sign in"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.experimental_rerun()
            else:
                st.error("Incorrect password.")
        return False
    return True


if not require_login():
    st.stop()

# ---------------------- AUTO-REFRESH ----------------------
REFRESH_INTERVAL_MS = 5_000
if _HAS_AUTORE:
    st_autorefresh(interval=REFRESH_INTERVAL_MS, limit=None, key="admin_autorefresh")

# ---------------------- HELPERS: load/parse data ----------------------
@st.cache_data(ttl=4)
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


def rating_badge_html(r):
    cls = f"r{int(r)}" if r in [1, 2, 3, 4, 5] else "r3"
    return f"<span class='rating-badge {cls}'>{int(r)}★</span>"

# ---------------------- PAGE HEADER ----------------------
df_raw = load_data()
df_raw = parse_timestamps(df_raw)

# Header
left_col, right_col = st.columns([3, 1])
with left_col:
    st.markdown("<div class='topbar'>", unsafe_allow_html=True)
    st.markdown("<div class='brand'>🛠 Admin — Feedback Console</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='subtitle'>Private dashboard — shows live submissions, AI summaries & suggested actions</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with right_col:
    # last refreshed
    st.metric("Last refreshed (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))

st.markdown("---")

# ---------------------- SIDEBAR FILTERS ----------------------
st.sidebar.header("Filters & Controls")
st.sidebar.markdown("Use filters to refine results. Auto-refresh runs every 5s if available.")

# Date range
today = datetime.utcnow().date()
default_from = today - timedelta(days=14)
date_range = st.sidebar.date_input("Date range (UTC)", value=(default_from, today))

# Ratings
rating_options = sorted(df_raw["rating"].dropna().unique().tolist(), reverse=True) if not df_raw.empty else [5, 4, 3, 2, 1]
selected_ratings = st.sidebar.multiselect("Ratings", options=rating_options, default=rating_options)

# Text search
text_query = st.sidebar.text_input("Search text (review/summary/actions)", value="")

# Download raw / clear cache
st.sidebar.markdown("---")
if st.sidebar.button("Clear cache & refresh"):
    try:
        load_data.clear()
    except Exception:
        pass
    st.experimental_rerun()

st.sidebar.markdown("Tip: mark this app PRIVATE at deploy time (Streamlit Cloud settings).")

# ---------------------- APPLY FILTERS ----------------------
df = df_raw.copy()
if not df.empty:
    # date filter
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

    # rating filter
    if selected_ratings:
        df = df[df["rating"].isin(selected_ratings)]

    # text search filter
    if text_query and text_query.strip() != "":
        q = text_query.strip().lower()
        mask = (
            df["review"].fillna("").str.lower().str.contains(q)
            | df["summary"].fillna("").str.lower().str.contains(q)
            | df["actions"].fillna("").str.lower().str.contains(q)
        )
        df = df[mask]

# ---------------------- KPI CARDS ----------------------
k1, k2, k3, k4 = st.columns([1.2, 1.2, 1.2, 1.2])
with k1:
    st.markdown("<div class='card kpi'><h3>Total feedback</h3><div class='value'>{}</div></div>".format(int(df.shape[0]) if not df.empty else 0), unsafe_allow_html=True)
with k2:
    avg_rating = round(df["rating"].astype(float).mean(), 2) if not df.empty else "—"
    st.markdown("<div class='card kpi'><h3>Average rating</h3><div class='value'>{}</div></div>".format(avg_rating), unsafe_allow_html=True)
with k3:
    last_sub = df["timestamp"].max() if not df.empty else "—"
    st.markdown("<div class='card kpi'><h3>Latest submission</h3><div class='value'>{}</div></div>".format(last_sub), unsafe_allow_html=True)
with k4:
    # average sentiment quick calc (lexicon)
    if not df.empty:
        text_blob = (df["summary"].fillna("") + " " + df["review"].fillna("") + " " + df["actions"].fillna("")).str.strip()
        POS = {"good", "great", "excellent", "love", "liked", "awesome", "nice", "satisfied", "happy", "pleasant", "fantastic", "amazing", "best"}
        NEG = {"bad", "terrible", "awful", "hate", "dislike", "poor", "unsatisfied", "unhappy", "problem", "issue", "worst", "bug"}
        def _score(s):
            if not isinstance(s, str) or s.strip()=="":
                return 0.0
            words = [w.strip(".,!?;:()[]\"'").lower() for w in s.split()]
            pos = sum(1 for w in words if w in POS)
            neg = sum(1 for w in words if w in NEG)
            return (pos - neg) / max(1, len(words))
        avg_sent = round(text_blob.apply(_score).mean(), 4)
    else:
        avg_sent = "—"
    st.markdown("<div class='card kpi'><h3>Avg sentiment (lexicon)</h3><div class='value'>{}</div></div>".format(avg_sent), unsafe_allow_html=True)

st.markdown("---")

# ---------------------- CHARTS & TABLE ----------------------
left, right = st.columns([2, 1])

with left:
    st.subheader("Rating distribution")
    if not df.empty:
        dist = df["rating"].value_counts().sort_index()
        st.bar_chart(dist)
    else:
        st.info("No data for distribution.")

    st.subheader("Rating trend (daily avg)")
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

with right:
    st.subheader("Quick actions")
    if not df.empty:
        st.write(f"Showing {int(df.shape[0])} results (filtered)")
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download filtered CSV", csv_bytes, file_name="feedback_filtered.csv", mime="text/csv")
    else:
        st.write("No results to download.")

st.markdown("---")

# ---------------------- RECENT SUBMISSIONS (paginated) ----------------------
st.subheader("Recent submissions (latest first)")
if not df.empty:
    df_sorted = df.sort_values("ts_parsed", ascending=False).reset_index(drop=True)
    # simple pagination
    page_size = 10
    total = len(df_sorted)
    pages = (total - 1) // page_size + 1
    page_idx = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1)
    start = (page_idx - 1) * page_size
    end = start + page_size
    subset = df_sorted.iloc[start:end]

    for _, row in subset.iterrows():
        badge = rating_badge_html(row.get("rating", 3))
        st.markdown(f"<div class='card' style='margin-bottom:10px'>", unsafe_allow_html=True)
        st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center'>", unsafe_allow_html=True)
        st.markdown(f"<div><strong>{row.get('timestamp','')}</strong></div>", unsafe_allow_html=True)
        st.markdown(f"<div>{badge}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small muted' style='margin-top:6px'>{row.get('review','')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin-top:8px'><strong>AI summary</strong></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small'>{row.get('summary','')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin-top:6px'><strong>AI actions</strong></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small'>{row.get('actions','')}</div>", unsafe_allow_html=True)
        if "sent_score" in row:
            st.markdown(f"<div style='margin-top:6px' class='muted small'>Sentiment: {round(row.get('sent_score',0.0),4)}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("No feedback matched the current filters.")

# ---------------------- FOOTER ----------------------
st.markdown("---")
st.markdown("<div class='muted small'>Pro tip: Deploy this app as PRIVATE (Streamlit Cloud Access Control). For production sharing between public and admin apps, point both to a shared DB (Postgres/Supabase) rather than a local CSV.</div>", unsafe_allow_html=True)

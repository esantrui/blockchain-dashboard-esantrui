"""CryptoChain Analyzer Dashboard — entry point.

Real-time Bitcoin blockchain intelligence built with Streamlit.
Auto-refreshes every 60 seconds so live data stays current.
"""

import time

import streamlit as st

from modules.m1_pow_monitor import render as render_m1
from modules.m2_block_header import render as render_m2
from modules.m3_difficulty_history import render as render_m3
from modules.m4_ai_component import render as render_m4

st.set_page_config(
    page_title="CryptoChain Analyzer",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "CryptoChain Analyzer — Real-time Bitcoin Analysis · UAX Cryptography Project"},
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d0d 0%, #161616 100%);
    }
    h1 {
        font-size: 2.4rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
    }
    [data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────
col_icon, col_title = st.columns([1, 6])
with col_icon:
    st.markdown("<h1 style='font-size:2.8rem'>🔗</h1>", unsafe_allow_html=True)
with col_title:
    st.title("CryptoChain Analyzer")
    st.markdown("*Real-time Bitcoin blockchain intelligence & cryptographic analysis*")

st.markdown("---")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Navigation")
    view = st.radio(
        "Module",
        [
            "🏠  Overview",
            "⛏️  M1 — PoW Monitor",
            "🔍  M2 — Block Header",
            "📈  M3 — Difficulty History",
            "🤖  M4 — AI Forecast",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown("### Auto-refresh")
    auto_refresh = st.toggle("Enable (60 s)", value=True, key="auto_refresh")
    if auto_refresh:
        st.caption("Page reloads every 60 s. M1 re-fetches live data automatically.")

    st.markdown("---")
    st.markdown(
        "**Project:** CryptoChain Analyzer  \n"
        "**Student:** Enrique · esantrui  \n"
        "**Course:** Cryptography · UAX 2025–26  \n"
        "**AI model:** ARIMA / Ensemble"
    )

# ── Module routing ─────────────────────────────────────────────────────────
if "Overview" in view:
    st.subheader("Dashboard overview")
    st.markdown(
        "Select a module from the sidebar to explore live Bitcoin data.  \n"
        "Each module connects the raw blockchain API data to the cryptographic "
        "theory studied in Topic 7."
    )

    cards = [
        ("⛏️ M1 — PoW Monitor",      "Live difficulty, inter-block time histogram (exponential distribution), and estimated network hash rate."),
        ("🔍 M2 — Block Header",      "80-byte header structure + step-by-step **hashlib** SHA256(SHA256(header)) verification against the target T."),
        ("📈 M3 — Difficulty History","Difficulty over time with adjustment events marked. Actual vs target block-time ratio from daily block counts."),
        ("🤖 M4 — AI Forecast",       "ARIMA, SARIMA, Holt-Winters, Linear Regression and Ensemble difficulty forecasting with holdout MAE/RMSE evaluation."),
    ]

    col_a, col_b = st.columns(2)
    for i, (title, desc) in enumerate(cards):
        col = col_a if i % 2 == 0 else col_b
        col.markdown(
            f"""
            <div style="
                background:linear-gradient(135deg,rgba(102,126,234,.10) 0%,rgba(118,75,162,.10) 100%);
                border:1px solid rgba(102,126,234,.30);
                border-radius:12px;padding:18px;margin-bottom:12px">
            <b>{title}</b><br><small style="color:#94a3b8">{desc}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        "**APIs used:** blockchain.info · api.blockchain.info · blockstream.info  \n"
        "**Framework:** Streamlit · Plotly  \n"
        "**How to run:** `pip install -r requirements.txt && streamlit run app.py`"
    )

elif "M1" in view:
    render_m1()
elif "M2" in view:
    render_m2()
elif "M3" in view:
    render_m3()
elif "M4" in view:
    render_m4()

# ── Auto-refresh (non-blocking: renders first, then sleeps, then reruns) ───
if auto_refresh:
    time.sleep(60)
    st.rerun()

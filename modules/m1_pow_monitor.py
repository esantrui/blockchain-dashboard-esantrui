"""Module M1 — Proof of Work Monitor.

Shows live data about the current state of Bitcoin mining:
  - Current difficulty and its visual representation as a leading-zero threshold.
  - Distribution of inter-block arrival times for the last N blocks (expected:
    exponential, because each hash attempt is an independent Bernoulli trial with
    the same probability p = 1/difficulty×2^32 of succeeding).
  - Estimated current network hash rate.
"""

import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import (
    count_leading_zero_bits,
    decode_bits,
    get_block,
    get_latest_block,
    get_recent_block_timestamps,
)

_CACHE_TTL = 60   # seconds before auto-refreshing live data


def _block_age_minutes(block_time: int) -> float:
    now = datetime.now(timezone.utc).timestamp()
    return max(0.0, (now - block_time) / 60.0)


def _render_hash_visual(block_hash: str, leading_zero_bits: int) -> None:
    zero_chars = leading_zero_bits // 4
    green_prefix = block_hash[:zero_chars]
    rest = block_hash[zero_chars:]

    st.markdown(
        "**Block hash (SHA-256d):** "
        f'<span style="color:#10b981;font-family:monospace;font-weight:700">{green_prefix}</span>'
        f'<span style="color:#94a3b8;font-family:monospace">{rest}</span>',
        unsafe_allow_html=True,
    )
    pct = leading_zero_bits / 256
    st.progress(pct, text=f"{leading_zero_bits} leading zero bits out of 256  (target coverage: {pct:.3%})")


def _render_target_explanation(bits: int) -> None:
    info = decode_bits(bits)
    bits_hex = f"{bits:08x}"
    st.markdown(
        "**`bits` field decoded** — compact 256-bit target encoding  \n"
        f"- Raw hex: `0x{bits_hex}`  \n"
        f"- Exponent: `{info['exponent']}` · Coefficient: `0x{info['coefficient_hex']}`  \n"
        f"- Full target (T): `0x{info['target_hex'][:20]}…`  \n"
        f"- Minimum leading zero **bytes** required: **{info['leading_zero_bytes']}**  \n"
        "- A valid hash must satisfy: `SHA256(SHA256(header)) < T`"
    )


def _render_hash_rate(difficulty: float) -> None:
    """Estimate and display the current network hash rate.

    Formula:  H = difficulty × 2^32 / 600
      - Each valid hash is found in 1/p trials where p ≈ 1 / (difficulty × 2^32)
      - Bitcoin targets 600 seconds per block
      - Therefore the network performs difficulty × 2^32 hashes every 600 seconds
    """
    hash_rate_hps = difficulty * (2 ** 32) / 600
    hash_rate_ehs = hash_rate_hps / 1e18

    st.subheader("Estimated network hash rate")
    col_h1, col_h2, col_h3 = st.columns(3)
    col_h1.metric("Hash rate (EH/s)", f"{hash_rate_ehs:.2f}")
    col_h2.metric("Hash rate (PH/s)", f"{hash_rate_ehs * 1000:.1f}")
    col_h3.metric("Difficulty", f"{difficulty:,.0f}")

    st.caption(
        "Estimate: `H = difficulty × 2³² / 600`  "
        "·  Actual rate fluctuates as mining pools join/leave the network."
    )


def _render_block_time_histogram(timestamps: list[int]) -> None:
    """Plot the distribution of inter-block arrival times.

    Theory: Bitcoin mining is a Poisson process. Each SHA-256 attempt has the
    same tiny probability p of producing a valid hash. The number of attempts
    follows a Geometric(p) distribution, which for large n and small p
    converges to an Exponential distribution with mean 600 s (10 min).

    We therefore expect inter-block times to follow Exp(λ = 1/600).
    """
    if len(timestamps) < 2:
        st.warning("Not enough blocks to plot the distribution.")
        return

    # Compute inter-block times in minutes (sorted newest → oldest)
    sorted_ts = sorted(timestamps, reverse=True)
    inter_times_s = [sorted_ts[i] - sorted_ts[i + 1] for i in range(len(sorted_ts) - 1)]
    inter_times_min = [t / 60.0 for t in inter_times_s if 0 < t < 3600]

    if not inter_times_min:
        st.warning("Could not compute valid inter-block times.")
        return

    n = len(inter_times_min)
    mean_min = float(np.mean(inter_times_min))
    median_min = float(np.median(inter_times_min))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Blocks sampled", n)
    c2.metric("Mean interval (min)", f"{mean_min:.2f}")
    c3.metric("Median interval (min)", f"{median_min:.2f}")
    c4.metric("Target (min)", "10.00")

    # ── Histogram ─────────────────────────────────────────────────────────
    arr = np.array(inter_times_min)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=arr,
        nbinsx=30,
        name="Observed",
        marker_color="rgba(59,130,246,0.7)",
        marker_line_color="rgba(59,130,246,1)",
        marker_line_width=0.5,
    ))

    # ── Theoretical exponential PDF overlay ───────────────────────────────
    # Exp with λ = 1/10 per minute (mean = 10 min)
    x_range = np.linspace(0, max(arr) * 1.1, 300)
    lam = 1 / 10.0             # rate = 1/mean (mean = 10 min target)
    bin_width = (arr.max() - arr.min()) / 30 if arr.max() > arr.min() else 1.0
    pdf_scaled = lam * np.exp(-lam * x_range) * n * bin_width

    fig.add_trace(go.Scatter(
        x=x_range,
        y=pdf_scaled,
        mode="lines",
        name="Exp(λ=1/10) — theoretical",
        line={"color": "#f59e0b", "width": 2, "dash": "dash"},
    ))

    # ── Empirical exponential fit ──────────────────────────────────────────
    lam_fit = 1 / mean_min
    pdf_fit = lam_fit * np.exp(-lam_fit * x_range) * n * bin_width
    fig.add_trace(go.Scatter(
        x=x_range,
        y=pdf_fit,
        mode="lines",
        name=f"Exp(λ=1/{mean_min:.1f}) — empirical fit",
        line={"color": "#10b981", "width": 2},
    ))

    fig.add_vline(
        x=10, line_dash="dot", line_color="#ef4444",
        annotation_text="10 min target", annotation_position="top right",
    )

    fig.update_layout(
        title=f"Inter-block time distribution  (last {n} blocks)",
        xaxis_title="Time between blocks (minutes)",
        yaxis_title="Count",
        template="plotly_dark",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        bargap=0.05,
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Why exponential? — theory", expanded=False):
        st.markdown(
            """
**Why do we expect an Exponential distribution?**

Bitcoin mining is a *memoryless* Poisson process:

1. Each SHA-256 hash attempt is an independent Bernoulli trial with probability
   `p ≈ 1 / (difficulty × 2³²)` of producing a valid hash.
2. The number of attempts until success is Geometric(p).
3. For large n and small p, Geometric(n, p) → Exponential(λ = n·p) — in the
   limit, mining success is a Poisson process with rate λ = network_hashrate × p.
4. For a constant target block time of 600 s, the network self-adjusts so the
   mean inter-arrival time stays at 10 minutes.

A histogram that resembles an exponential (long right tail, mode near 0)
confirms the network is behaving as expected. Significant deviations can
indicate sudden hash-rate changes or mining pool coordination.
            """
        )


def _fetch_live_data() -> dict | None:
    """Fetch the latest block and recent timestamps; return a data dict."""
    latest = get_latest_block()
    block = get_block(latest["hash"])
    timestamps = get_recent_block_timestamps(50)
    return {
        "block": block,
        "timestamps": timestamps,
        "fetched_at": time.time(),
    }


def render() -> None:
    """Render the M1 panel — Proof of Work Monitor."""
    st.header("M1 — Proof of Work Monitor")
    st.write("Live view of Bitcoin mining: current difficulty, inter-block time distribution, and hash rate.")

    with st.expander("Theory: leading zeros, bits field, and exponential arrivals", expanded=False):
        st.markdown(
            """
**Leading zero bits** — Bitcoin's SHA-256d block hash must begin with a certain
number of zero *bits* to be valid. Each additional zero bit **halves** the probability
that a random hash passes, so it **doubles** the expected mining work.
The current network requires roughly 76–78 leading zero bits.

**`bits` field (compact target)** — The 4-byte `bits` field encodes the 256-bit
target T in compact form:  `T = coefficient × 2^(8 × (exponent − 3))`

**Inter-block times** — Because each hash attempt is an independent Bernoulli trial,
the time between blocks follows an **Exponential distribution** with mean 600 s.

**Hash rate** — Estimated as `difficulty × 2³² / 600`  (hashes per second).
            """
        )

    # ── Auto-load: use session state cache with TTL ────────────────────────
    cached = st.session_state.get("m1_data")
    data_age = time.time() - cached["fetched_at"] if cached else _CACHE_TTL + 1

    col_btn, col_age = st.columns([1, 3])
    if col_btn.button("Refresh now", key="m1_fetch") or data_age > _CACHE_TTL:
        with st.spinner("Fetching live data…"):
            try:
                st.session_state["m1_data"] = _fetch_live_data()
                cached = st.session_state["m1_data"]
                col_age.success("Data refreshed.")
            except Exception as exc:
                st.error(f"Error fetching data: {exc}")
                if not cached:
                    return

    if not cached:
        st.info("Click **Refresh now** to load live Bitcoin data.")
        return

    block = cached["block"]
    timestamps = cached["timestamps"]
    fetched_at = cached["fetched_at"]
    age_sec = int(time.time() - fetched_at)
    st.caption(f"Data age: {age_sec}s  ·  auto-refreshes after {_CACHE_TTL}s  ·  last updated {datetime.fromtimestamp(fetched_at).strftime('%H:%M:%S')}")

    # ── Metric cards ──────────────────────────────────────────────────────
    st.divider()
    age_minutes = _block_age_minutes(int(block.get("time", 0)))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Height", f"{block.get('height', '-'):,}")
    col2.metric("Transactions", f"{block.get('n_tx', '-'):,}")
    col3.metric("Nonce", f"{block.get('nonce', '-'):,}")
    col4.metric("Bits (hex)", f"0x{block.get('bits', 0):08x}")

    col5, col6 = st.columns(2)
    col5.metric("Block age (min)", f"{age_minutes:,.2f}")
    col6.metric("Size (bytes)", f"{block.get('size', '-'):,}")

    # ── Cryptographic PoW analysis ────────────────────────────────────────
    st.divider()
    block_hash = block.get("hash", "")
    leading_zero_bits = count_leading_zero_bits(block_hash)

    st.subheader("Proof of Work snapshot")
    _render_hash_visual(block_hash, leading_zero_bits)
    st.markdown(f"**Previous block:** `{block.get('prev_block', '-')}`")
    st.divider()
    _render_target_explanation(block.get("bits", 0))

    # ── Estimated hash rate ───────────────────────────────────────────────
    st.divider()
    bits_info = decode_bits(block.get("bits", 0))
    target_int = int(bits_info["target_hex"], 16)
    max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    difficulty = max_target / target_int if target_int else 0
    _render_hash_rate(difficulty)

    # ── Inter-block time distribution ─────────────────────────────────────
    st.divider()
    st.subheader("Inter-block time distribution (last 50 blocks)")
    _render_block_time_histogram(timestamps)

    # ── Hash distribution pie ─────────────────────────────────────────────
    st.divider()
    st.subheader("Hash bit distribution")
    df_bits = pd.DataFrame({
        "Segment": ["Leading zero bits", "Remaining bits"],
        "Bits": [leading_zero_bits, 256 - leading_zero_bits],
    })
    fig = px.pie(
        df_bits,
        names="Segment",
        values="Bits",
        hole=0.6,
        color="Segment",
        color_discrete_map={
            "Leading zero bits": "#10b981",
            "Remaining bits": "#1e2637",
        },
        title=f"256-bit hash space — {leading_zero_bits} leading zero bits (PoW proof)",
    )
    fig.update_traces(textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw block data"):
        st.json(block)

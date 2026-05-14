"""Module M3 — Difficulty History.

Plots Bitcoin mining difficulty over time, marks difficulty adjustment events
(every ~2016 blocks ≈ 2 weeks), and shows the ratio of actual average block
time to the 600-second target for each period.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from api.blockchain_client import get_blocks_per_day_history, get_difficulty_history

_TARGET_BLOCKS_PER_DAY = 144   # 24 h × 60 min/h / 10 min/block
_HOVERMODE = "x unified"


def _render_difficulty_chart(df: pd.DataFrame, show_ma: bool, log_scale: bool) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Difficulty"],
        name="Difficulty",
        line={"color": "#3b82f6", "width": 1.5},
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.06)",
    ))
    if show_ma:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["MA14"],
            name="MA-14",
            line={"color": "#f59e0b", "width": 1.5, "dash": "dash"},
        ))
    adj_df = df[df["is_adjustment"]]
    if not adj_df.empty:
        fig.add_trace(go.Scatter(
            x=adj_df["Date"], y=adj_df["Difficulty"],
            mode="markers", name="Adjustment event",
            marker={
                "symbol": "diamond", "size": 9, "color": "#a78bfa",
                "line": {"color": "#7c3aed", "width": 1.5},
            },
        ))
    fig.update_layout(
        title="Bitcoin Mining Difficulty",
        xaxis_title="Date", yaxis_title="Difficulty",
        yaxis_type="log" if log_scale else "linear",
        template="plotly_dark",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        hovermode=_HOVERMODE,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_adjustment_delta(df: pd.DataFrame) -> None:
    adj_delta_df = df[df["is_adjustment"]].copy()
    if adj_delta_df.empty:
        return
    st.subheader("Difficulty adjustment Δ% at each event")
    colors = ["#10b981" if v >= 0 else "#ef4444" for v in adj_delta_df["Delta_pct"]]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=adj_delta_df["Date"], y=adj_delta_df["Delta_pct"],
        name="Δ% at adjustment", marker_color=colors,
    ))
    fig2.add_hline(y=0, line_color="rgba(255,255,255,0.3)", line_dash="dot")
    fig2.update_layout(
        xaxis_title="Date", yaxis_title="Difficulty change (%)",
        template="plotly_dark", hovermode=_HOVERMODE,
    )
    st.plotly_chart(fig2, use_container_width=True)


def _render_block_time_ratio(bpd_values: list) -> None:
    st.subheader("Actual average block time vs 600-second target")
    st.markdown(
        "The chart shows the ratio `actual_blocks_per_day / 144`.  \n"
        "A ratio **above 1** means blocks arrived **faster** than the target.  \n"
        "A ratio **below 1** means blocks arrived **slower** than the target.  \n"
        "Difficulty increases when the ratio is consistently above 1, and decreases when below."
    )
    bpd_df = pd.DataFrame(bpd_values)
    bpd_df["x"] = pd.to_datetime(bpd_df["x"], unit="s")
    bpd_df = bpd_df.rename(columns={"x": "Date", "y": "BlocksPerDay"})
    bpd_df["Ratio"] = bpd_df["BlocksPerDay"] / _TARGET_BLOCKS_PER_DAY
    bpd_df["AvgBlockTime_s"] = 86400 / bpd_df["BlocksPerDay"].replace(0, float("nan"))

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Avg ratio (period)", f"{bpd_df['Ratio'].mean():.3f}")
    col_r2.metric("Min avg block time", f"{bpd_df['AvgBlockTime_s'].min():.0f} s")
    col_r3.metric("Max avg block time", f"{bpd_df['AvgBlockTime_s'].max():.0f} s")

    colors_ratio = [
        "#10b981" if r >= 1.0 else "#ef4444"
        for r in bpd_df["Ratio"].fillna(1.0)
    ]
    fig3 = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("Blocks per day (target = 144)", "Actual / target ratio"),
        vertical_spacing=0.08,
    )
    fig3.add_trace(go.Bar(
        x=bpd_df["Date"], y=bpd_df["BlocksPerDay"],
        name="Blocks/day", marker_color="rgba(59,130,246,0.7)",
    ), row=1, col=1)
    fig3.add_hline(y=_TARGET_BLOCKS_PER_DAY, line_dash="dot", line_color="#f59e0b",
                   row=1, col=1, annotation_text="144 target")
    fig3.add_trace(go.Bar(
        x=bpd_df["Date"], y=bpd_df["Ratio"],
        name="Actual/target ratio", marker_color=colors_ratio,
    ), row=2, col=1)
    fig3.add_hline(y=1.0, line_dash="dot", line_color="#f59e0b",
                   row=2, col=1, annotation_text="1.0 = on target")
    fig3.update_layout(
        template="plotly_dark", showlegend=False, hovermode=_HOVERMODE, height=500,
    )
    fig3.update_yaxes(title_text="Blocks/day", row=1, col=1)
    fig3.update_yaxes(title_text="Ratio", row=2, col=1)
    st.plotly_chart(fig3, use_container_width=True)


def _load_data(n_points: int, show_ratio: bool) -> bool:
    """Fetch and cache difficulty + blocks-per-day data. Returns True on success."""
    try:
        diff_values = get_difficulty_history(n_points)
        if not diff_values:
            st.warning("No difficulty data returned by the API.")
            return False
        st.session_state["m3_diff"] = diff_values
    except Exception as exc:
        st.error(f"Error loading difficulty data: {exc}")
        return False

    if show_ratio:
        try:
            st.session_state["m3_bpd"] = get_blocks_per_day_history(n_points)
        except Exception:
            st.session_state["m3_bpd"] = []
    return True


def render() -> None:
    """Render the M3 panel — Difficulty History."""
    st.header("M3 — Difficulty History")
    st.write(
        "Evolution of Bitcoin mining difficulty over time, with adjustment events marked "
        "and the ratio of actual average block time to the 600-second target."
    )

    with st.expander("Theory: difficulty adjustment and the 600-second target", expanded=False):
        st.markdown(
            """
**Difficulty** is derived from the 256-bit target T:  `difficulty = difficulty_1_target / T`

A difficulty of D means a miner must perform ≈ D × 2³² hashes on average to find a valid block.

**Adjustment rule** (every 2016 blocks ≈ 2 weeks):
```
new_target = old_target × (actual_time_2016_blocks / 1_209_600 s)
```
This keeps the average inter-block time at **600 seconds (10 minutes)**.
The adjustment is capped at ×4 / ÷4 per period to prevent wild oscillations.

**Actual / target ratio** = `actual_blocks_per_day / 144`.
Values above 1 mean faster-than-target mining; values below 1 mean slower.
            """
        )

    n_points = st.slider("Difficulty data points", min_value=10, max_value=365, value=120, key="m3_n")
    col_opts = st.columns(3)
    show_ma    = col_opts[0].checkbox("Moving average (14 pts)", value=True,  key="m3_ma")
    log_scale  = col_opts[1].checkbox("Log scale (difficulty)",  value=False, key="m3_log")
    show_ratio = col_opts[2].checkbox("Show block-time ratio",   value=True,  key="m3_ratio")

    if st.button("Load charts", key="m3_load"):
        with st.spinner("Fetching data…"):
            if not _load_data(n_points, show_ratio):
                return

    diff_values = st.session_state.get("m3_diff")
    if diff_values is None:
        st.info("Click **Load charts** to display the difficulty history.")
        return

    # ── Build difficulty DataFrame ─────────────────────────────────────────
    df = pd.DataFrame(diff_values)
    df["x"] = pd.to_datetime(df["x"], unit="s")
    df = df.rename(columns={"x": "Date", "y": "Difficulty"})
    if show_ma:
        df["MA14"] = df["Difficulty"].rolling(14).mean()
    df["Delta_pct"]    = df["Difficulty"].pct_change() * 100
    df["is_adjustment"] = df["Delta_pct"].abs() > 0.5

    first_val     = float(df["Difficulty"].iloc[0])
    last_val      = float(df["Difficulty"].iloc[-1])
    max_val       = float(df["Difficulty"].max())
    pct_change    = ((last_val - first_val) / first_val) * 100 if first_val else 0.0
    n_adjustments = int(df["is_adjustment"].sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Latest difficulty",   f"{last_val:.3e}")
    c2.metric("Period start",        f"{first_val:.3e}")
    c3.metric("Period change",       f"{pct_change:+.2f}%")
    c4.metric("Period high",         f"{max_val:.3e}")
    c5.metric("Adjustments detected", n_adjustments)

    _render_difficulty_chart(df, show_ma, log_scale)
    _render_adjustment_delta(df)

    bpd_values = st.session_state.get("m3_bpd", [])
    if show_ratio and bpd_values:
        _render_block_time_ratio(bpd_values)
    elif show_ratio:
        st.info("Blocks-per-day data unavailable (API may have rate-limited the request).")

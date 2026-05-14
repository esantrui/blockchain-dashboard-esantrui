"""Module M4 — AI Component.

Forecasting Bitcoin mining difficulty with ARIMA, Holt-Winters, and
Linear Regression, plus an Ensemble model. Includes:
  - Holdout evaluation (MAE, RMSE) for model comparison
  - Confidence intervals (±1 σ of training residuals, expanding with horizon)
  - Anomaly detection via Z-score
"""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from api.blockchain_client import get_difficulty_history


# ---------------------------------------------------------------------------
# Model implementations
# ---------------------------------------------------------------------------

def _fit_arima(train: pd.Series, horizon: int) -> tuple[list[float], list[float], str]:
    """ARIMA(1,2,1): double-differencing makes the difficulty series stationary."""
    model = ARIMA(train, order=(1, 2, 1))
    fitted = model.fit()
    forecast_res = fitted.get_forecast(steps=horizon)
    yhat = forecast_res.predicted_mean
    ci = forecast_res.conf_int(alpha=0.32)   # ~±1 σ  (68% CI)
    lower = ci.iloc[:, 0].tolist()
    upper = ci.iloc[:, 1].tolist()
    return (
        [max(0.0, float(v)) for v in yhat],
        list(zip([max(0.0, l) for l in lower], [max(0.0, u) for u in upper])),
        "ARIMA(1,2,1)",
    )


def _fit_sarima(train: pd.Series, horizon: int) -> tuple[list[float], list[float], str]:
    """SARIMA with weekly seasonality — captures 7-day mining pool patterns."""
    try:
        model = SARIMAX(
            train,
            order=(0, 2, 1),
            seasonal_order=(0, 1, 1, 7),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fitted = model.fit(disp=False)
        label = "SARIMA(0,2,1)×(0,1,1,7)"
    except Exception:
        model = SARIMAX(
            train,
            order=(1, 1, 1),
            seasonal_order=(0, 1, 1, 7),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fitted = model.fit(disp=False)
        label = "SARIMA(1,1,1)×(0,1,1,7)"

    forecast_res = fitted.get_forecast(steps=horizon)
    yhat = forecast_res.predicted_mean
    ci = forecast_res.conf_int(alpha=0.32)
    lower = ci.iloc[:, 0].tolist()
    upper = ci.iloc[:, 1].tolist()
    return (
        [max(0.0, float(v)) for v in yhat],
        list(zip([max(0.0, l) for l in lower], upper)),
        label,
    )


def _fit_holtwinters(train: pd.Series, horizon: int) -> tuple[list[float], list[float], str]:
    """Holt-Winters additive trend + additive seasonality (period=7 days)."""
    model = ExponentialSmoothing(
        train,
        trend="add",
        seasonal="add",
        seasonal_periods=7,
        initialization_method="estimated",
    )
    fitted = model.fit(optimized=True)
    yhat = fitted.forecast(horizon)

    # Build empirical CI from in-sample residuals (expand with horizon)
    res_std = float(fitted.resid.std())
    ci = [
        (max(0.0, float(v) - res_std * (1 + i * 0.04)),
         max(0.0, float(v) + res_std * (1 + i * 0.04)))
        for i, v in enumerate(yhat)
    ]
    return [max(0.0, float(v)) for v in yhat], ci, "Holt-Winters(add,add,7)"


def _fit_linear(train: pd.Series, horizon: int) -> tuple[list[float], list[float], str]:
    """Linear regression on time index — global trend baseline."""
    n = len(train)
    xs = np.arange(n, dtype=float)
    ys = train.values.astype(float)
    coeffs = np.polyfit(xs, ys, deg=1)
    slope, intercept = coeffs[0], coeffs[1]

    residuals = ys - (slope * xs + intercept)
    res_std = float(residuals.std())

    future_xs = np.arange(n, n + horizon, dtype=float)
    yhat = [max(0.0, slope * x + intercept) for x in future_xs]
    ci = [
        (max(0.0, v - res_std * (1 + i * 0.04)),
         max(0.0, v + res_std * (1 + i * 0.04)))
        for i, v in enumerate(yhat)
    ]
    return yhat, ci, "Linear Regression"


def _fit_and_forecast(
    train: pd.Series, horizon: int, model_name: str
) -> tuple[list[float], list[tuple[float, float]], str]:
    """Dispatch to the selected model. Returns (forecast, ci_pairs, label)."""
    if model_name == "ARIMA":
        return _fit_arima(train, horizon)
    if model_name == "SARIMA":
        return _fit_sarima(train, horizon)
    if model_name == "Holt-Winters":
        return _fit_holtwinters(train, horizon)
    if model_name == "Linear Regression":
        return _fit_linear(train, horizon)
    # Ensemble: average of ARIMA, Holt-Winters, and Linear Regression
    arima_fc, arima_ci, _ = _fit_arima(train, horizon)
    hw_fc, hw_ci, _ = _fit_holtwinters(train, horizon)
    lr_fc, lr_ci, _ = _fit_linear(train, horizon)
    ensemble_fc = [
        max(0.0, (a + b + c) / 3)
        for a, b, c in zip(arima_fc, hw_fc, lr_fc)
    ]
    ensemble_ci = [
        (min(ac[0], hc[0], lc[0]), max(ac[1], hc[1], lc[1]))
        for ac, hc, lc in zip(arima_ci, hw_ci, lr_ci)
    ]
    return ensemble_fc, ensemble_ci, "Ensemble (ARIMA + HW + LR)"


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------

def _mae(y_true: pd.Series, y_pred: list[float]) -> float:
    n = min(len(y_true), len(y_pred))
    return sum(abs(float(a) - float(b)) for a, b in zip(y_true[:n], y_pred[:n])) / n if n else 0.0


def _rmse(y_true: pd.Series, y_pred: list[float]) -> float:
    n = min(len(y_true), len(y_pred))
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(y_true[:n], y_pred[:n])) / n) if n else 0.0


def _mape(y_true: pd.Series, y_pred: list[float]) -> float:
    """Mean Absolute Percentage Error — useful for scale-independent comparison."""
    n = min(len(y_true), len(y_pred))
    errors = [
        abs((float(a) - float(b)) / float(a))
        for a, b in zip(y_true[:n], y_pred[:n])
        if float(a) != 0.0
    ]
    return (sum(errors) / len(errors)) * 100 if errors else 0.0


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def _detect_anomalies(series: pd.Series, threshold: float = 2.0) -> pd.Series:
    """Return boolean mask for points with |z-score| >= threshold.

    A high z-score means the difficulty value deviated significantly from
    the mean — this can indicate unusual mining pool activity or a rapid
    hash-rate change.
    """
    mean = series.mean()
    std = series.std(ddof=0)
    if std == 0:
        return pd.Series([False] * len(series), index=series.index)
    return ((series - mean) / std).abs() >= threshold


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render() -> None:
    """Render the M4 panel — AI Forecasting Component."""
    st.header("M4 — AI Component")
    st.write("Difficulty forecasting with ARIMA, SARIMA, Holt-Winters, Linear Regression, and Ensemble.")

    with st.expander("Model guide & evaluation methodology", expanded=False):
        st.markdown(
            """
| Model | Strengths | Best for |
|---|---|---|
| **ARIMA(1,2,1)** | Handles autocorrelation; double-differencing removes trend | Short-horizon, volatile series |
| **SARIMA** | Adds weekly seasonality on top of ARIMA | Series with 7-day patterns |
| **Holt-Winters** | Explicit level + trend + seasonal decomposition | Smoother, medium-horizon |
| **Linear Regression** | Simple global trend; interpretable slope | Long-horizon baseline |
| **Ensemble** | Averages all three; reduces model-specific bias | General use (recommended) |

**Evaluation:** each model is trained on the first 80% of data and evaluated on
the final 20% (holdout). MAE and RMSE are reported on that holdout set —
lower is better. **MAPE** is scale-independent and useful for comparing across
periods with very different difficulty magnitudes.

**Confidence intervals** are ±1 σ of in-sample residuals, expanding linearly
with the forecast horizon to reflect increasing uncertainty.
            """
        )

    # ── Controls ──────────────────────────────────────────────────────────
    history_points = st.slider("Training points (days)", min_value=30, max_value=365, value=180, key="m4_hist")
    forecast_horizon = st.slider("Forecast horizon (days)", min_value=7, max_value=90, value=30, key="m4_horizon")
    anomaly_threshold = st.slider("Anomaly Z-score threshold", min_value=1.0, max_value=4.0, value=2.0, step=0.5, key="m4_sigma")
    model_choice = st.selectbox(
        "Forecasting model",
        ["ARIMA", "SARIMA", "Holt-Winters", "Linear Regression", "Ensemble"],
        index=4,
        key="m4_model",
    )

    if st.button("Run AI analysis", key="m4_run"):
        with st.spinner(f"Fetching data and running {model_choice}…"):
            try:
                values = get_difficulty_history(history_points)
                if not values:
                    st.warning("No difficulty data returned by the API.")
                    return

                df = pd.DataFrame(values)
                df["x"] = pd.to_datetime(df["x"], unit="s")
                df = df.rename(columns={"x": "Date", "y": "Difficulty"})

                holdout_size = max(7, min(30, len(df) // 5))
                if len(df) <= holdout_size + 14:
                    st.warning("Not enough data points. Increase the training window.")
                    return

                train_series = df["Difficulty"].iloc[:-holdout_size]
                holdout_series = df["Difficulty"].iloc[-holdout_size:]
                full_series = df["Difficulty"]

                # ── Holdout evaluation ─────────────────────────────────────
                holdout_pred, _, _ = _fit_and_forecast(train_series, holdout_size, model_choice)
                h_mae = _mae(holdout_series, holdout_pred)
                h_rmse = _rmse(holdout_series, holdout_pred)
                h_mape = _mape(holdout_series, holdout_pred)

                # ── Full forecast with CI ──────────────────────────────────
                forecast, ci_pairs, model_label = _fit_and_forecast(full_series, forecast_horizon, model_choice)

                last_date = df["Date"].iloc[-1]
                future_dates = pd.date_range(
                    last_date + pd.Timedelta(days=1),
                    periods=forecast_horizon,
                    freq="D",
                )

                ci_lower = [p[0] for p in ci_pairs]
                ci_upper = [p[1] for p in ci_pairs]

                # ── Anomaly detection ──────────────────────────────────────
                anomaly_mask = _detect_anomalies(full_series, threshold=anomaly_threshold)
                anomaly_df = df.loc[anomaly_mask, ["Date", "Difficulty"]].copy()
                anomaly_df["Z-score"] = (
                    (full_series[anomaly_mask] - full_series.mean()) / full_series.std(ddof=0)
                ).abs().round(2)

                # ── Summary metrics ────────────────────────────────────────
                c1, c2, c3 = st.columns(3)
                c1.metric("Latest value", f"{float(full_series.iloc[-1]):,.3e}")
                c2.metric("Forecast end (+{} d)".format(forecast_horizon), f"{float(forecast[-1]):,.3e}")
                delta_pct = (float(forecast[-1]) - float(full_series.iloc[-1])) / float(full_series.iloc[-1]) * 100
                c3.metric("Forecast Δ", f"{delta_pct:+.2f}%")

                c4, c5, c6, c7 = st.columns(4)
                c4.metric("Holdout MAE", f"{h_mae:,.3e}")
                c5.metric("Holdout RMSE", f"{h_rmse:,.3e}")
                c6.metric("Holdout MAPE", f"{h_mape:.2f}%")
                c7.metric("Anomalies", int(anomaly_df.shape[0]), help=f"Points with |z| ≥ {anomaly_threshold}")

                # ── Forecast chart with CI ─────────────────────────────────
                fig = go.Figure()

                # Confidence interval band
                fig.add_trace(go.Scatter(
                    x=pd.concat([pd.Series(future_dates), pd.Series(future_dates[::-1])]),
                    y=ci_upper + ci_lower[::-1],
                    fill="toself",
                    fillcolor="rgba(139,92,246,0.15)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name="CI ±1σ",
                    hoverinfo="skip",
                ))

                # Historical difficulty
                fig.add_trace(go.Scatter(
                    x=df["Date"], y=df["Difficulty"],
                    name="History",
                    line=dict(color="#3b82f6", width=1.5),
                    fill="tozeroy",
                    fillcolor="rgba(59,130,246,0.04)",
                ))

                # Forecast line
                fig.add_trace(go.Scatter(
                    x=future_dates, y=forecast,
                    name=f"Forecast ({model_label})",
                    line=dict(color="#8b5cf6", width=2, dash="dash"),
                ))

                # Anomaly markers
                if not anomaly_df.empty:
                    fig.add_trace(go.Scatter(
                        x=anomaly_df["Date"], y=anomaly_df["Difficulty"],
                        name="Anomaly",
                        mode="markers",
                        marker=dict(color="#ef4444", size=8, symbol="triangle-up"),
                    ))

                fig.update_layout(
                    title=f"Difficulty: History + {model_label} Forecast (±1σ CI)",
                    xaxis_title="Date",
                    yaxis_title="Difficulty",
                    template="plotly_dark",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── Model comparison table ─────────────────────────────────
                st.subheader("Model comparison on holdout set")
                comparison_rows = []
                for m in ["ARIMA", "Holt-Winters", "Linear Regression", "Ensemble"]:
                    try:
                        p, _, lbl = _fit_and_forecast(train_series, holdout_size, m)
                        comparison_rows.append({
                            "Model": lbl,
                            "MAE": f"{_mae(holdout_series, p):.3e}",
                            "RMSE": f"{_rmse(holdout_series, p):.3e}",
                            "MAPE (%)": f"{_mape(holdout_series, p):.2f}",
                        })
                    except Exception:
                        pass
                if comparison_rows:
                    st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)

                # ── Anomaly table ──────────────────────────────────────────
                if anomaly_df.empty:
                    st.success(f"No anomalies detected (|z| ≥ {anomaly_threshold}).")
                else:
                    st.warning(f"**{len(anomaly_df)} anomalies** detected with |z| ≥ {anomaly_threshold}.")
                    st.dataframe(
                        anomaly_df.rename(columns={"Difficulty": "Difficulty value"}).assign(
                            **{"Difficulty value": anomaly_df["Difficulty"].map(lambda x: f"{x:.3e}")}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                st.caption(f"Model: {model_label}  ·  Training points: {len(train_series)}  ·  Holdout: {holdout_size} days")

            except Exception as exc:
                st.error(f"Error in AI component: {exc}")
    else:
        st.info("Select parameters and click **Run AI analysis**.")
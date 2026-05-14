[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/N3kLi3ZO)
[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=23640731&assignment_repo_type=AssignmentRepo)
# CryptoChain Analyzer Dashboard

Real-time Bitcoin blockchain intelligence — SHA-256 Proof of Work analysis, difficulty history, and AI-powered forecasting.

## Student Information

| Field | Value |
|---|---|
| Student Name | Enrique Ruiz Santos |
| GitHub Username | esantrui |
| Project Title | CryptoChain Analyzer |
| Chosen AI Approach | Predictor — ARIMA / Ensemble difficulty forecasting |

## Module Tracking

| Module | Description | Status |
|---|---|---|
| M1 | Proof of Work Monitor | ✅ Done |
| M2 | Block Header Analyzer | ✅ Done |
| M3 | Difficulty History | ✅ Done |
| M4 | AI Component | ✅ Done |

## Current Progress

- **M1** — Live block metrics (height, nonce, bits), inter-block time histogram with exponential distribution fit and theoretical overlay, estimated network hash rate (`H = difficulty × 2³² / 600`). Data auto-refreshes every 60 s via session-state cache.
- **M2** — Full step-by-step local Proof of Work verification using Python `hashlib`: reconstructs the 80-byte header from raw fields, computes `SHA256(SHA256(header))`, confirms the result matches the API hash, and verifies hash < target. Cross-checks against Blockstream raw header bytes.
- **M3** — Difficulty over time with moving average, adjustment events marked with diamond markers, Δ% bar chart at each event, and a dual-panel chart showing actual blocks/day vs the 144/day target (ratio chart).
- **M4** — Difficulty forecasting with ARIMA(1,2,1), SARIMA, Holt-Winters, Linear Regression, and Ensemble model. Holdout evaluation (MAE, RMSE, MAPE) and anomaly detection via Z-score.
- **App** — Auto-refresh every 60 s (non-blocking), Overview home page, dark-theme UI with gradient header.

## Next Step

- Add the final PDF report to the `report/` folder before the deadline.

## Main Problem or Blocker

- None. All four modules are complete and operational. Auto-refresh works without extra packages.

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`. Select a module from the sidebar; M1 auto-fetches live data on load.

## Project Structure

```text
blockchain-dashboard-esantrui/
├── README.md
├── requirements.txt
├── app.py                        # Dashboard entry point + auto-refresh
├── api/
│   └── blockchain_client.py      # blockchain.info + Blockstream API helpers
├── modules/
│   ├── m1_pow_monitor.py         # PoW Monitor + histogram + hash rate
│   ├── m2_block_header.py        # Block Header + hashlib verification
│   ├── m3_difficulty_history.py  # Difficulty History + ratio chart
│   └── m4_ai_component.py        # AI Forecasting (ARIMA/Ensemble)
└── report/
    └── (PDF report — added before deadline)
```

<!-- student-repo-auditor:teacher-feedback:start -->
## Teacher Feedback

### Kick-off Review

Review time: 2026-04-29 20:31 CEST
Status: Amber

Strength:
- I can see the dashboard structure integrating the checkpoint modules.

Improve now:
- M2 still needs clearer block-header verification with hashlib and target logic.

Next step:
- Add local block-header verification with hashlib and show the Proof of Work check clearly.
<!-- student-repo-auditor:teacher-feedback:end -->

## APIs Used

| API | URL | Used for |
|---|---|---|
| blockchain.info | `blockchain.info/api` | Block data, latestblock, rawblock |
| Blockchain.info Charts | `api.blockchain.info/charts` | Difficulty history, avg-confirmation-time |
| Blockstream | `blockstream.info/api` | Raw 80-byte header hex, recent block timestamps |

"""
Generate the final project report as a PDF using fpdf2.
Run from the project root:  python report/generate_report.py
Output:  report/report.pdf
"""

from fpdf import FPDF, XPos, YPos

OUTPUT = "report/report.pdf"

# -- Colour palette ----------------------------------------------------------
BLUE      = (37,  99, 235)   # accent / headings
DARK      = (26,  26, 26)    # body text
GREY      = (100, 100, 100)  # captions / running header
LIGHT_BG  = (244, 247, 251)  # table even rows / code bg
TABLE_HDR = (30,  58,  95)   # table header bg (dark blue)
WHITE     = (255, 255, 255)
GREEN_ROW = (240, 253, 244)  # best-result highlight row


class Report(FPDF):

    # -- Running header & footer --------------------------------------------
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6,
                  "CryptoChain Analyzer Dashboard  .  Enrique Ruiz Santos  .  UAX Cryptography 2025-26",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*GREY)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.set_draw_color(*GREY)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")

    # -- Helper methods -----------------------------------------------------
    def h1(self, text):
        self.ln(5)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*BLUE)
        self.cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # underline
        y = self.get_y()
        self.set_draw_color(*BLUE)
        self.set_line_width(0.5)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(3)

    def h2(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*BLUE)
        self.cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body(self, text, indent=0):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK)
        self.set_x(self.l_margin + indent)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK)
        x0 = self.l_margin + 4
        self.set_x(x0)
        self.cell(4, 5.5, chr(149))          # bullet char
        self.multi_cell(self.w - self.r_margin - x0 - 4, 5.5, text)

    def code_line(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(*LIGHT_BG)
        self.set_text_color(*BLUE)
        self.set_x(self.l_margin + 4)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 4, 5.5, text, fill=True)
        self.ln(1)

    def highlight_box(self, text):
        """Light-blue info box."""
        self.set_fill_color(239, 246, 255)
        self.set_draw_color(*BLUE)
        self.set_line_width(0.4)
        x = self.l_margin
        w = self.w - self.l_margin - self.r_margin
        # estimate height
        self.set_font("Helvetica", "", 9.5)
        lines = self.multi_cell(w - 6, 5, text, dry_run=True, output="LINES")
        h = len(lines) * 5 + 6
        self.rect(x, self.get_y(), w, h, style="FD")
        self.set_xy(x + 3, self.get_y() + 3)
        self.set_text_color(*DARK)
        self.multi_cell(w - 6, 5, text)
        self.ln(3)

    def table(self, headers, rows, col_widths=None, highlight_row=None):
        """Simple table with header row and alternating row colours."""
        usable = self.w - self.l_margin - self.r_margin
        if col_widths is None:
            col_widths = [usable / len(headers)] * len(headers)

        # Header row
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*TABLE_HDR)
        self.set_text_color(*WHITE)
        self.set_x(self.l_margin)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=0, fill=True, align="L")
        self.ln()

        # Data rows
        self.set_font("Helvetica", "", 9)
        for ridx, row in enumerate(rows):
            self.set_x(self.l_margin)
            if highlight_row is not None and ridx == highlight_row:
                self.set_fill_color(*GREEN_ROW)
            elif ridx % 2 == 0:
                self.set_fill_color(*LIGHT_BG)
            else:
                self.set_fill_color(*WHITE)
            self.set_text_color(*DARK)

            # Multi-line cells: compute max lines
            max_lines = 1
            for ci, cell_text in enumerate(row):
                self.set_font("Helvetica", "", 9)
                lines = self.multi_cell(col_widths[ci], 5.5, cell_text,
                                        dry_run=True, output="LINES")
                max_lines = max(max_lines, len(lines))
            row_h = max_lines * 5.5

            x_start = self.l_margin
            y_start = self.get_y()
            for ci, cell_text in enumerate(row):
                self.set_xy(x_start, y_start)
                self.set_fill_color(
                    *GREEN_ROW if (highlight_row is not None and ridx == highlight_row)
                    else (LIGHT_BG if ridx % 2 == 0 else WHITE)
                )
                self.multi_cell(col_widths[ci], row_h / max_lines,
                                 cell_text, fill=True, align="L")
                x_start += col_widths[ci]
            self.set_y(y_start + row_h)

        # Bottom border line
        self.set_draw_color(*BLUE)
        self.set_line_width(0.5)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(4)


# -- Build the report --------------------------------------------------------

pdf = Report(orientation="P", unit="mm", format="A4")
pdf.set_margins(20, 18, 20)
pdf.set_auto_page_break(auto=True, margin=18)
pdf.add_page()

# -- Title page block --------------------------------------------------------
pdf.set_font("Helvetica", "B", 22)
pdf.set_text_color(*DARK)
pdf.cell(0, 12, "CryptoChain Analyzer Dashboard", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_font("Helvetica", "", 11)
pdf.set_text_color(*GREY)
pdf.cell(0, 6, "Final Project Report -- Hash Functions and Blockchain",
         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
pdf.cell(0, 6, "Cryptography  |  Universidad Alfonso X el Sabio  |  Prof. Jorge Calvo  |  AY 2025-26",
         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_font("Helvetica", "B", 11)
pdf.set_text_color(*DARK)
pdf.cell(0, 7, "Enrique Ruiz Santos  .  esantrui  .  May 2026",
         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_draw_color(*GREY)
pdf.set_line_width(0.4)
pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.w - pdf.r_margin, pdf.get_y() + 2)
pdf.ln(6)

# -- 1  Introduction ----------------------------------------------------------
pdf.h1("1  Introduction")
pdf.body(
    "This report documents the CryptoChain Analyzer Dashboard, a real-time Python dashboard "
    "built with Streamlit that connects to public Bitcoin blockchain APIs and displays live "
    "cryptographic metrics. The project was developed as the individual assessment for the "
    "Cryptography course at Universidad Alfonso X el Sabio (AY 2025-26), under the supervision "
    "of Prof. Jorge Calvo."
)
pdf.body(
    "The dashboard implements all four required modules (M1-M4). Data is sourced from three "
    "free public APIs: Blockstream, Blockchain.info, and the Blockchain.info Charts API. "
    "The page auto-refreshes every 60 seconds so all metrics stay current without manual "
    "intervention."
)

# -- 2  Cryptographic Metrics -------------------------------------------------
pdf.h1("2  Cryptographic Metrics")

pdf.h2("2.1  SHA-256d and Proof of Work (M1, M2)")
pdf.body(
    "SHA-256d (double SHA-256) is Bitcoin's standard cryptographic hash: "
    "SHA256(SHA256(data)). Bitcoin's Proof-of-Work requires miners to find a nonce such "
    "that SHA256d(header) <= target. The 80-byte block header contains six fields, all "
    "stored in little-endian byte order:"
)
for item in [
    "version (4 B) -- signals which BIP consensus rules apply",
    "previous block hash (32 B) -- SHA-256d of the preceding header; the chain link",
    "Merkle root (32 B) -- root of the transaction hash tree",
    "timestamp (4 B) -- Unix epoch in seconds",
    "bits (4 B) -- compact encoding of the 256-bit PoW target threshold",
    "nonce (4 B) -- miner-controlled counter iterated until the hash is valid",
]:
    pdf.bullet(item)
pdf.ln(2)

pdf.body(
    "Module M2 parses all six fields and verifies the PoW locally using Python's built-in "
    "hashlib and struct modules -- no external cryptographic library is used. The verification "
    "proceeds in six explicit steps visible in the dashboard: (1) reconstruct the 80-byte "
    "header from the API fields, (2) compute SHA256(header), (3) compute SHA256 again, "
    "(4) reverse bytes to display order, (5) compare with the API-returned hash, "
    "(6) confirm the result is numerically less than the decoded target."
)

pdf.highlight_box(
    "bits -> target decoding:  target = coefficient x 2^(8 x (exponent - 3))\n"
    "where exponent = bits >> 24  and  coefficient = bits & 0x00FFFFFF.\n"
    "A valid hash, interpreted as a 256-bit unsigned integer, must be <= target.\n"
    "At current difficulty, approximately 79 leading bits must be zero: P(valid) ~= 2^-79."
)

pdf.table(
    headers=["Field", "Example value", "Meaning"],
    rows=[
        ["bits (hex)",        "0x17021FF0",           "Compact target stored in block header"],
        ["Exponent byte",     "0x17 = 23",            "target = coeff x 2^(8x(23-3)) = coeff x 2^160"],
        ["Coefficient",       "0x021FF0",             "Mantissa of the compact representation"],
        ["Full 256-bit target","00000000021FF0...00", "Hash must be <= this value"],
        ["Leading zero bits", "~79 / 256",            "P(valid hash) ~= 2^-79"],
    ],
    col_widths=[38, 42, 90],
)

pdf.h2("2.2  Difficulty and Network Hash Rate (M1, M3)")
pdf.body(
    "The difficulty value is derived from the target by comparing it to the genesis block "
    "target (bits = 0x1d00ffff):"
)
pdf.code_line("difficulty = genesis_target / current_target")
pdf.body("The estimated network hash rate follows from the expected hashes per block and the 600-second target:")
pdf.code_line("hashrate ~= difficulty x 2^32 / 600   [H/s]")
pdf.body(
    "At current difficulty (~1.1 x 10^14) this yields approximately 790 EH/s (exahashes "
    "per second), consistent with public mining pool statistics."
)
pdf.body("Bitcoin adjusts difficulty every 2,016 blocks (~14 days):")
pdf.code_line("new_difficulty = old_difficulty x (actual_time_for_2016_blocks / 1,209,600 s)")
pdf.body(
    "The ratio is clamped to [1/4, 4] to prevent extreme swings. Module M3 charts this "
    "history, marks each adjustment event with a diamond marker, and plots the block-time "
    "ratio per epoch derived analytically from consecutive difficulty values: "
    "actual_block_time / 600 = D_old / D_new."
)

pdf.h2("2.3  Inter-Block Time Distribution (M1)")
pdf.body(
    "Module M1 fetches timestamps for the last 50 blocks via the Blockstream API and plots "
    "the distribution of inter-block arrival times. The expected distribution is "
    "Exponential(lambda = 1/600) because:"
)
for item in [
    "Each SHA-256 hash attempt is an independent Bernoulli trial with probability "
    "p ~= 1 / (difficulty x 2^32) of success.",
    "The number of attempts until success is Geometric(p), which for large n and small p "
    "converges to an Exponential distribution.",
    "The network self-adjusts so the mean inter-arrival time stays at 10 minutes.",
]:
    pdf.bullet(item)
pdf.ln(2)
pdf.body(
    "The histogram is overlaid with both the theoretical Exp(lambda = 1/10 min) curve and "
    "an empirical fit, confirming the Poisson-process nature of Bitcoin mining."
)

# -- Page 2 -------------------------------------------------------------------
pdf.add_page()

# -- 3  AI Component -----------------------------------------------------------
pdf.h1("3  AI Component -- M4: Difficulty Predictor")

pdf.h2("3.1  Problem Statement")
pdf.body(
    "The goal of Module M4 is to predict the next Bitcoin mining difficulty adjustment "
    "value using a time-series model trained on historical difficulty data fetched from "
    "the Blockchain.info Charts API. An accurate forecast helps miners and analysts "
    "anticipate profitability changes before the next 2,016-block epoch closes."
)

pdf.h2("3.2  Model Choice and Justification")
pdf.body("Four models are implemented and compared on a holdout set (last 20 % of data, no shuffle):")

pdf.table(
    headers=["Model", "Rationale", "Key parameter"],
    rows=[
        ["ARIMA(1,2,1)",
         "Double-differencing removes Bitcoin's strong upward trend making the series "
         "stationary. AR(1) captures first-order autocorrelation.",
         "d = 2 (integrated order)"],
        ["SARIMA(0,2,1)x(0,1,1,7)",
         "Extends ARIMA with a seasonal component (period = 7 days) to capture weekly "
         "mining pool patterns.",
         "Seasonal period s = 7"],
        ["Holt-Winters",
         "Explicit triple-exponential smoothing (additive trend + additive seasonality). "
         "Robust for medium-horizon forecasts.",
         "seasonal_periods = 7"],
        ["Linear Regression",
         "Global trend baseline -- fits a straight line through the time index. "
         "Interpretable and computationally cheap.",
         "deg = 1 (OLS)"],
        ["Ensemble",
         "Simple average of ARIMA, Holt-Winters, and Linear Regression. Reduces "
         "model-specific variance; recommended for general use.",
         "Equal weights (1/3 each)"],
    ],
    col_widths=[42, 100, 28],
)

pdf.body(
    "Why time-series models over deep learning? LSTM and Prophet require substantially "
    "more data and longer training time. The difficulty series, sampled approximately "
    "daily, provides ~180 training points -- sufficient for ARIMA/ETS-class models but "
    "borderline for neural approaches. The ensemble strategy further reduces the risk of "
    "any single model's bias dominating the forecast."
)

pdf.h2("3.3  Evaluation Results")
pdf.body(
    "Each model is trained on the first 80 % of data and evaluated on a 30-day holdout "
    "set. Metrics are computed from real blockchain.info difficulty data (180 data points, "
    "difficulty range: 1.26e14 to 1.55e14). Confidence intervals shown in the dashboard "
    "are +/-1 sigma of in-sample residuals, expanding linearly with the forecast horizon."
)

pdf.table(
    headers=["Model", "MAE", "RMSE", "MAPE (%)", "Notes"],
    rows=[
        ["ARIMA(1,2,1)",      "1.36e+13", "1.60e+13", "10.17 %",
         "Overreacts to short-term volatility"],
        ["SARIMA",            "~ARIMA",   "~ARIMA",   "~10 %",
         "Seasonal term has limited effect on difficulty"],
        ["Holt-Winters",      "4.79e+12", "5.38e+12", "3.59 %",
         "Best single model on this period"],
        ["Linear Regression", "1.32e+12", "1.73e+12", "0.97 %",
         "Best overall -- difficulty trended linearly over 180 days"],
        ["Ensemble",          "5.98e+12", "7.01e+12", "4.48 %",
         "More robust across different market regimes"],
    ],
    col_widths=[40, 20, 20, 18, 72],
    highlight_row=3,   # Linear Regression row (0-indexed)
)

pdf.highlight_box(
    "Interpretation: Linear Regression achieves the lowest MAPE (0.97 %) on this holdout "
    "because Bitcoin difficulty followed an approximately linear upward trend over the last "
    "180 days. The Ensemble model sacrifices some in-sample accuracy for better generalisation "
    "when the regime changes (e.g. sudden hash-rate drops). The dashboard presents all five "
    "models with their holdout metrics so the user can choose the most appropriate one."
)

pdf.h2("3.4  Anomaly Detection (M4 -- built-in)")
pdf.body(
    "An anomaly detector is integrated into M4. For each data point in the difficulty "
    "series, a Z-score is computed:"
)
pdf.code_line("z = (D_i - mean) / std")
pdf.body(
    "Points with |z| >= threshold (default 2.0) are flagged as anomalies and displayed "
    "as red triangles on the forecast chart. In the difficulty context, anomalies correspond "
    "to unusually large or small adjustment events -- possible indicators of sudden hash-rate "
    "changes, mining pool exits, or coordinated attacks on the network."
)

# -- 4  Technical Implementation -----------------------------------------------
pdf.h1("4  Technical Implementation")
pdf.body(
    "The dashboard is built with Streamlit using a sidebar navigation structure with five "
    "pages (Overview + M1-M4). Charts are rendered with Plotly graph_objects. The project "
    "has no external cryptographic dependencies: all SHA-256 operations use Python's "
    "built-in hashlib and struct modules."
)

pdf.table(
    headers=["Component", "Details"],
    rows=[
        ["APIs",
         "Blockstream (block data, raw headers, recent timestamps); "
         "Blockchain.info (rawblock, latestblock); "
         "Blockchain.info Charts (difficulty history, avg-confirmation-time)"],
        ["Machine Learning",
         "statsmodels ARIMA, SARIMAX, ExponentialSmoothing; "
         "numpy polyfit for Linear Regression"],
        ["Frontend",
         "Streamlit, Plotly graph_objects, custom dark-theme CSS with gradient header"],
        ["Cryptography",
         "hashlib.sha256 (SHA-256d), struct (little-endian header parsing) -- no external library"],
        ["Auto-refresh",
         "60-second non-blocking refresh (time.sleep(60) + st.rerun()); "
         "M1 uses session-state caching with 60-second TTL"],
        ["Error handling",
         "All API calls wrapped in try/except; stale cached data used as fallback. "
         "M3 stores data in session_state so it persists across auto-refreshes."],
    ],
    col_widths=[42, 128],
)

# -- 5  References -------------------------------------------------------------
pdf.h1("5  References")
refs = [
    ("Nakamoto, S. (2008).",
     "Bitcoin: A Peer-to-Peer Electronic Cash System. https://bitcoin.org/bitcoin.pdf. "
     "Cited for §6 (mining incentives), §7 (difficulty recalculation), §11 (attack probability)."),
    ("Blockstream.",
     "Esplora REST API Documentation. "
     "https://github.com/Blockstream/esplora/blob/master/API.md. "
     "Used for block raw headers and recent block timestamps (M1, M2)."),
    ("Blockchain.com.",
     "Charts API -- Difficulty and Hash Rate. https://www.blockchain.com/explorer/charts. "
     "Used for historical difficulty data and average confirmation time (M3, M4)."),
    ("Seabold, S. & Perktold, J. (2010).",
     "statsmodels: Econometric and statistical modeling with Python. "
     "Proceedings of the 9th Python in Science Conference. https://www.statsmodels.org. "
     "ARIMA/SARIMAX/Holt-Winters implementation (M4)."),
    ("Bitcoin Wiki.",
     "Block hashing algorithm. https://en.bitcoin.it/wiki/Block_hashing_algorithm. "
     "Reference for 80-byte header structure and byte-order conventions (M2)."),
]
for i, (bold_part, rest) in enumerate(refs, 1):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*DARK)
    label = f"[{i}]  {bold_part} "
    pdf.cell(pdf.get_string_width(label) + 1, 5.5, label)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, rest)
    pdf.ln(1)

# -- Save ---------------------------------------------------------------------
pdf.output(OUTPUT)
print(f"Report saved to {OUTPUT}")

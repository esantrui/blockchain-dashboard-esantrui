"""Module M2 — Block Header Analyzer.

Displays the 80-byte Bitcoin block header structure, decodes the 'bits'
field into the full 256-bit PoW target, and verifies the Proof of Work
locally using Python's hashlib — no third-party cryptographic library needed.

Key educational point: miners do not check a pre-computed hash; they repeatedly
modify the nonce and re-hash until SHA256(SHA256(header)) < target.
"""

import hashlib
import struct
from datetime import datetime, timezone

import streamlit as st

from api.blockchain_client import (
    build_header_bytes,
    compute_double_sha256,
    count_leading_zero_bits,
    decode_bits,
    get_block,
    get_block_header_hex,
    get_latest_block,
)


def _to_utc(unix_ts: int) -> str:
    """Format a UNIX timestamp as a UTC datetime string."""
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _render_hash_bits(block_hash: str, leading_zero_bits: int) -> None:
    """Render the hash with leading zeros highlighted in green."""
    zero_chars = leading_zero_bits // 4
    green_part = block_hash[:zero_chars]
    rest_part = block_hash[zero_chars:]

    st.markdown(
        f'<span style="color:#10b981;font-family:monospace;font-weight:700;font-size:0.85rem">{green_part}</span>'
        f'<span style="color:#94a3b8;font-family:monospace;font-size:0.85rem">{rest_part}</span>',
        unsafe_allow_html=True,
    )
    pct = leading_zero_bits / 256
    st.progress(
        pct,
        text=(
            f"{leading_zero_bits} leading zero bits  —  "
            f"probability of random hash passing: 1 in 2^{leading_zero_bits} ≈ "
            f"{2**leading_zero_bits:.2e}"
        ),
    )


def _render_hashlib_verification(block: dict) -> None:
    """Show step-by-step SHA256(SHA256(header)) verification using Python hashlib.

    This is the core of M2: we reconstruct the exact 80-byte header from the
    block's fields, feed it into hashlib, and confirm the result matches the
    hash the API returned — all without trusting any external library.
    """
    st.subheader("Local Proof of Work verification with hashlib")
    st.markdown(
        "Bitcoin miners find a nonce such that `SHA256(SHA256(header)) < target`.  \n"
        "We reproduce this computation locally using Python's built-in `hashlib`."
    )

    bits_val = int(block.get("bits", 0))
    api_hash = block.get("hash", "")

    # ── Step 1: Build the 80-byte header ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Step 1 — Reconstruct the 80-byte header")
    st.markdown(
        "The header is built from six fields, each encoded in **little-endian** byte order.  \n"
        "`prev_block` and `mrkl_root` are stored in internal byte order (reversed from the "
        "display hex string returned by the API)."
    )

    ver = int(block.get("ver", 1))
    prev_block = block.get("prev_block", "0" * 64).zfill(64)
    mrkl_root  = block.get("mrkl_root",  "0" * 64).zfill(64)
    timestamp  = int(block.get("time",   0))
    nonce      = int(block.get("nonce",  0))

    field_rows = [
        ("version",        "0–3",   f"struct.pack('<I', {ver})",           struct.pack("<I", ver).hex()),
        ("prev block hash","4–35",  "bytes.fromhex(prev_block)[::-1]",     bytes.fromhex(prev_block)[::-1].hex()),
        ("Merkle root",    "36–67", "bytes.fromhex(mrkl_root)[::-1]",      bytes.fromhex(mrkl_root)[::-1].hex()),
        ("timestamp",      "68–71", f"struct.pack('<I', {timestamp})",      struct.pack("<I", timestamp).hex()),
        ("bits",           "72–75", f"struct.pack('<I', {bits_val})",       struct.pack("<I", bits_val).hex()),
        ("nonce",          "76–79", f"struct.pack('<I', {nonce})",          struct.pack("<I", nonce).hex()),
    ]

    import pandas as pd
    df_fields = pd.DataFrame(field_rows, columns=["Field", "Bytes", "Python expression", "Hex bytes"])
    st.dataframe(df_fields, use_container_width=True, hide_index=True)

    header_bytes = build_header_bytes(block)
    assert len(header_bytes) == 80
    st.markdown("**Full 80-byte header:**")
    st.code(header_bytes.hex(), language="text")
    st.caption(f"Header length: {len(header_bytes)} bytes ✓")

    # ── Step 2: First SHA256 pass ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Step 2 — SHA256(header)")
    sha256_1 = hashlib.sha256(header_bytes).digest()
    st.code(
        "import hashlib\n"
        "round1 = hashlib.sha256(header_bytes).digest()\n"
        f"# → {sha256_1.hex()}",
        language="python",
    )

    # ── Step 3: Second SHA256 pass ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Step 3 — SHA256(SHA256(header))  — internal byte order")
    sha256_2 = hashlib.sha256(sha256_1).digest()
    st.code(
        "round2 = hashlib.sha256(round1).digest()  # Bitcoin double-hash\n"
        f"# → {sha256_2.hex()}",
        language="python",
    )

    # ── Step 4: Reverse to display order ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Step 4 — Reverse bytes → display order")
    computed_hash = sha256_2[::-1].hex()
    st.code(
        "block_hash = round2[::-1].hex()  # internal → display order\n"
        f"# → {computed_hash}",
        language="python",
    )

    # ── Step 5: Compare with API hash ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Step 5 — Compare with API-returned hash")
    col_a, col_b = st.columns(2)
    col_a.markdown("**Computed by hashlib:**")
    col_a.code(computed_hash, language="text")
    col_b.markdown("**Returned by blockchain.info API:**")
    col_b.code(api_hash, language="text")

    if computed_hash == api_hash:
        st.success(
            "✓  **MATCH** — our locally-computed hash equals the API hash.  \n"
            "The header fields were correctly reconstructed and the double-SHA256 is consistent."
        )
    else:
        st.error(
            "✗  **MISMATCH** — the computed hash does not match the API hash.  \n"
            "This usually means a field was decoded with the wrong byte order."
        )

    # ── Step 6: Verify hash < target ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Step 6 — Verify hash < target  (Proof of Work check)")
    target_info = decode_bits(bits_val)
    target_int  = int(target_info["target_hex"], 16)
    hash_int    = int(computed_hash, 16)

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("hash  (as integer)", f"{hash_int:.4e}")
    col_t2.metric("target T (as integer)", f"{target_int:.4e}")
    col_t3.metric("hash < target?", "YES ✓" if hash_int < target_int else "NO ✗")

    st.code(
        f"bits       = 0x{bits_val:08x}\n"
        f"exponent   = {target_info['exponent']}\n"
        f"coefficient= 0x{target_info['coefficient_hex'].upper()}\n"
        f"target  T  = 0x{target_info['target_hex']}\n"
        f"block hash = 0x{computed_hash}\n\n"
        f"hash < T   → {'True  ← Proof of Work satisfied ✓' if hash_int < target_int else 'False ← INVALID block'}",
        language="text",
    )

    if hash_int < target_int:
        lz = count_leading_zero_bits(computed_hash)
        st.success(
            f"✓  **Proof of Work verified locally** — hash < target.  \n"
            f"The block hash has **{lz} leading zero bits**, confirming the miner performed "
            f"≈ 2^{lz} ≈ {2**lz:.2e} hash attempts on average."
        )
    else:
        st.error("✗  hash ≥ target — Proof of Work is NOT satisfied.")

    # ── Blockstream cross-check ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Cross-check — raw header from Blockstream API")
    st.markdown(
        "As an extra sanity check we also fetch the raw header hex directly from "
        "Blockstream and compare it with our reconstruction."
    )
    try:
        raw_hex = get_block_header_hex(api_hash)
        col_x1, col_x2 = st.columns(2)
        col_x1.markdown("**Our reconstruction:**")
        col_x1.code(header_bytes.hex(), language="text")
        col_x2.markdown("**Blockstream raw header:**")
        col_x2.code(raw_hex, language="text")

        if header_bytes.hex().lower() == raw_hex.lower():
            st.success("✓  Header bytes match Blockstream — reconstruction is correct.")
        else:
            st.warning("⚠  Minor mismatch vs Blockstream (possible API field difference).")
    except Exception as exc:
        st.info(f"Blockstream cross-check unavailable: {exc}")

    st.caption("All computations performed locally with Python's built-in `hashlib` and `struct` modules.")


def render() -> None:
    """Render the M2 panel — Block Header Analyzer."""
    st.header("M2 — Block Header Analyzer")
    st.write(
        "Inspect the 80-byte Bitcoin block header, decode the target, "
        "and **verify Proof of Work locally with hashlib** — no external tools needed."
    )

    with st.expander("Theory: the 80-byte header and the bits→target decoding", expanded=False):
        st.markdown(
            """
Bitcoin's block header is exactly **80 bytes**, structured as six fields:

| Field | Bytes | Encoding | Description |
|---|---|---|---|
| Version | 4 | 32-bit LE int | Block version number |
| Previous block hash | 32 | internal byte order | SHA-256d of the preceding header |
| Merkle root | 32 | internal byte order | Root of the transaction Merkle tree |
| Timestamp | 4 | 32-bit LE int | UNIX time of block creation |
| **Bits** | **4** | **32-bit LE int** | **Compact encoding of the 256-bit PoW target** |
| Nonce | 4 | 32-bit LE int | 32-bit counter miners iterate over |

**`bits` → full 256-bit target:**
```
T = coefficient × 2^(8 × (exponent − 3))
```
- `exponent` = most-significant byte of `bits`
- `coefficient` = lower 3 bytes of `bits`

**Proof of Work:**  miners hash the 80-byte header with `SHA256(SHA256(header))`.
The nonce is incremented on every attempt. When the resulting hash is numerically
less than T, the block is valid. Counting **leading zero bits** in the hash
confirms the constraint was met.

**Byte order note:**  `prev_block` and `mrkl_root` are stored in *internal byte order*
(reversed from the hex string shown in block explorers). Version, timestamp, bits,
and nonce are 32-bit little-endian integers.
            """
        )

    # ── Block hash input ───────────────────────────────────────────────────
    col_btn, _ = st.columns([1, 3])
    if col_btn.button("Use latest block", key="m2_latest"):
        try:
            latest = get_latest_block()
            st.session_state["m2_hash"] = latest.get("hash", "")
        except Exception as exc:
            st.error(f"Could not fetch latest block hash: {exc}")

    block_hash_input = st.text_input(
        "Block hash (64 hex characters)",
        placeholder="Enter a 64-character block hash or click 'Use latest block'…",
        key="m2_hash",
    ).strip()

    if st.button("Analyze block", key="m2_lookup") and block_hash_input:
        with st.spinner("Fetching block data…"):
            try:
                block = get_block(block_hash_input)
                st.session_state["m2_block"] = block
            except Exception as exc:
                st.error(f"Error fetching block: {exc}")

    block = st.session_state.get("m2_block")
    if not block:
        st.info("Enter a block hash and click **Analyze block**, or click **Use latest block** first.")
        return

    # ── Header field metrics ───────────────────────────────────────────────
    st.divider()
    st.subheader("80-byte header fields")
    cols = st.columns(4)
    cols[0].metric("Version", f"0x{block.get('ver', 0):08x}")
    cols[1].metric("Height", f"{block.get('height', '-'):,}")
    cols[2].metric("Nonce", f"{block.get('nonce', '-'):,}")
    cols[3].metric("Transactions", f"{block.get('n_tx', '-'):,}")

    col_a, col_b = st.columns(2)
    col_a.metric("Bits (hex)", f"0x{block.get('bits', 0):08x}")
    col_b.metric("Size", f"{block.get('size', 0):,} bytes")

    st.write(f"**Previous block:** `{block.get('prev_block', '-')}`")
    st.write(f"**Merkle root:**    `{block.get('mrkl_root', '-')}`")
    if block.get("time") is not None:
        st.write(f"**Timestamp (UTC):** {_to_utc(int(block['time']))}")

    # ── Target decoding ────────────────────────────────────────────────────
    st.divider()
    bits_val = block.get("bits", 0)
    target_info = decode_bits(bits_val)

    st.subheader("Target decoding (bits field)")
    t1, t2, t3 = st.columns(3)
    t1.metric("Exponent (e)", target_info["exponent"])
    t2.metric("Coefficient", f"0x{target_info['coefficient_hex'].upper()}")
    t3.metric("Min leading zero bytes", target_info["leading_zero_bytes"])

    st.code(
        f"bits       = 0x{bits_val:08x}\n"
        f"exponent   = {target_info['exponent']}\n"
        f"coefficient= 0x{target_info['coefficient_hex'].upper()}\n"
        f"target T   = 0x{target_info['target_hex']}\n"
        f"\nA valid hash must satisfy:  SHA256(SHA256(header)) < T",
        language="text",
    )

    # ── Quick hash visual ──────────────────────────────────────────────────
    st.divider()
    st.subheader("Leading-zero bit pattern")
    block_hash = block.get("hash", "")
    leading_zero_bits = count_leading_zero_bits(block_hash)
    st.markdown("**Hash (green = leading zero bits, proof of work):**")
    _render_hash_bits(block_hash, leading_zero_bits)

    # ── hashlib verification (main M2 feature) ─────────────────────────────
    st.divider()
    _render_hashlib_verification(block)

    with st.expander("Raw block JSON"):
        st.json(block)

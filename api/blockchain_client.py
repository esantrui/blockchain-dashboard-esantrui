"""
Blockchain API client.

Provides helper functions to fetch Bitcoin data from public APIs.
All endpoints are unauthenticated and free to use.
"""

import hashlib
import struct
import requests

BASE_URL = "https://blockchain.info"
CHARTS_BASE_URL = "https://api.blockchain.info"
BLOCKSTREAM_URL = "https://blockstream.info/api"


# ---------------------------------------------------------------------------
# Blockchain.info endpoints
# ---------------------------------------------------------------------------

def get_latest_block() -> dict:
    """Return the latest block summary (height, hash, time)."""
    response = requests.get(f"{BASE_URL}/latestblock", timeout=10)
    response.raise_for_status()
    return response.json()


def get_block(block_hash: str) -> dict:
    """Return full block details from blockchain.info.

    Key fields:
      - bits   : compact 256-bit target (see decode_bits)
      - nonce  : 32-bit value miners iterate to satisfy hash < target
      - hash   : SHA-256d of the 80-byte header; must start with enough zeros
      - ver    : version integer
      - prev_block : previous block hash (display order / big-endian hex)
      - mrkl_root  : Merkle root (display order / big-endian hex)
      - time   : UNIX timestamp
    """
    response = requests.get(f"{BASE_URL}/rawblock/{block_hash}", timeout=10)
    response.raise_for_status()
    return response.json()


def get_difficulty_history(n_points: int = 100) -> list[dict]:
    """Return the last *n_points* difficulty values as [{x: unix_ts, y: diff}, ...]."""
    response = requests.get(
        f"{CHARTS_BASE_URL}/charts/difficulty",
        params={"timespan": "1year", "format": "json", "sampled": "true"},
        timeout=10,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "application/json" not in content_type.lower():
        raise ValueError("Difficulty endpoint did not return JSON data.")

    data = response.json()
    values = data.get("values", [])
    if not isinstance(values, list):
        raise ValueError("Unexpected difficulty response format.")
    return values[-n_points:]


def get_avg_confirmation_time(n_points: int = 90) -> list[dict]:
    """Return daily average transaction confirmation time [{x: unix_ts, y: minutes}, ...].

    The confirmation time is the average time from broadcast to first confirmation.
    Dividing by 10 gives the actual/target block-time ratio (target = 10 minutes).
    Source: blockchain.info avg-confirmation-time chart.
    """
    response = requests.get(
        f"{CHARTS_BASE_URL}/charts/avg-confirmation-time",
        params={"timespan": "1year", "format": "json", "sampled": "true"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    values = data.get("values", [])
    return values[-n_points:]


# ---------------------------------------------------------------------------
# Blockstream endpoints
# ---------------------------------------------------------------------------

def get_blockstream_block(block_hash: str) -> dict:
    """Return block details from Blockstream API (alternative source)."""
    response = requests.get(f"{BLOCKSTREAM_URL}/block/{block_hash}", timeout=10)
    response.raise_for_status()
    return response.json()


def get_block_header_hex(block_hash: str) -> str:
    """Fetch the raw 80-byte block header from Blockstream as a hex string.

    This is the exact sequence of bytes that miners feed into SHA256.
    """
    response = requests.get(f"{BLOCKSTREAM_URL}/block/{block_hash}/header", timeout=10)
    response.raise_for_status()
    return response.text.strip()


def get_recent_block_timestamps(n: int = 50) -> list[int]:
    """Return UNIX timestamps of the last n blocks from Blockstream, newest first.

    Used to compute inter-block arrival times for the M1 histogram.
    Blockstream returns 25 blocks per call; multiple calls are made if n > 25.
    """
    timestamps: list[int] = []
    url = f"{BLOCKSTREAM_URL}/blocks"

    while len(timestamps) < n:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        blocks = resp.json()
        if not blocks:
            break
        for b in blocks:
            timestamps.append(int(b["timestamp"]))
        last_height = int(blocks[-1]["height"])
        url = f"{BLOCKSTREAM_URL}/blocks/{last_height - 1}"

    return sorted(timestamps[:n], reverse=True)


# ---------------------------------------------------------------------------
# Cryptographic helpers — connecting API fields to PoW theory
# ---------------------------------------------------------------------------

def count_leading_zero_bits(block_hash_hex: str) -> int:
    """Count leading zero bits in a hex-encoded SHA-256d block hash.

    Theory: each extra leading-zero bit halves the probability that a random
    hash satisfies the target, so it doubles the expected mining work.
    A Bitcoin hash is 256 bits; the current network requires ~76 leading zeros.
    """
    count = 0
    for char in block_hash_hex:
        nibble = int(char, 16)
        if nibble == 0:
            count += 4          # all 4 bits of this nibble are zero
        else:
            # count zero bits before the first 1-bit in this nibble
            count += 3 - int(nibble.bit_length() - 1)
            break
    return count


def decode_bits(bits: int) -> dict:
    """Decode the compact 'bits' field into the full 256-bit PoW target.

    The bits field encodes the target T as:
        T = coefficient × 2^(8 × (exponent − 3))

    where:
        exponent    = bits >> 24          (most-significant byte)
        coefficient = bits & 0x00FFFFFF   (lower 3 bytes)

    A valid block must satisfy:  SHA256(SHA256(header)) < T
    The smaller T is, the more leading zeros are required and the harder
    the puzzle — this is what 'difficulty' measures.
    """
    exponent = (bits >> 24) & 0xFF
    coefficient = bits & 0x00FFFFFF

    # Reconstruct full 256-bit target as a big integer
    target_int = coefficient * (2 ** (8 * (exponent - 3)))

    # Format as 64-character zero-padded hex string (256 bits = 32 bytes)
    target_hex = f"{target_int:064x}"

    # Number of leading zero bytes required (each zero byte = 8 leading zero bits)
    leading_zero_bytes = max(0, 32 - exponent)

    return {
        "exponent": exponent,
        "coefficient": coefficient,
        "coefficient_hex": f"{coefficient:06x}",
        "target_hex": target_hex,
        "leading_zero_bytes": leading_zero_bytes,
    }


def build_header_bytes(block: dict) -> bytes:
    """Construct the 80-byte block header from the fields returned by blockchain.info.

    Header layout (all integers are little-endian):
        Bytes  0– 3  : version (4 bytes, LE)
        Bytes  4–35  : previous block hash (32 bytes, internal/reversed order)
        Bytes 36–67  : Merkle root (32 bytes, internal/reversed order)
        Bytes 68–71  : timestamp (4 bytes, LE)
        Bytes 72–75  : bits / target (4 bytes, LE)
        Bytes 76–79  : nonce (4 bytes, LE)

    The API returns 'prev_block' and 'mrkl_root' in display order (big-endian
    hex). We reverse them to get internal byte order used inside the header.
    """
    ver = int(block.get("ver", 1))
    prev_block = block.get("prev_block", "0" * 64).zfill(64)
    mrkl_root = block.get("mrkl_root", "0" * 64).zfill(64)
    timestamp = int(block.get("time", 0))
    bits = int(block.get("bits", 0))
    nonce = int(block.get("nonce", 0))

    header = struct.pack("<I", ver)                # 4 bytes — version (LE)
    header += bytes.fromhex(prev_block)[::-1]      # 32 bytes — prev hash (reversed)
    header += bytes.fromhex(mrkl_root)[::-1]       # 32 bytes — Merkle root (reversed)
    header += struct.pack("<I", timestamp)         # 4 bytes — timestamp (LE)
    header += struct.pack("<I", bits)              # 4 bytes — bits/target (LE)
    header += struct.pack("<I", nonce)             # 4 bytes — nonce (LE)

    return header   # exactly 80 bytes


def compute_double_sha256(header_bytes: bytes) -> str:
    """Compute SHA256(SHA256(header)) and return the display-order hex hash.

    Bitcoin's double-hash produces an internal-order (little-endian) 32-byte
    digest. Reversing the bytes gives the display order that matches the hash
    shown in block explorers and returned by the API.
    """
    round1 = hashlib.sha256(header_bytes).digest()
    round2 = hashlib.sha256(round1).digest()
    return round2[::-1].hex()   # reverse → display order

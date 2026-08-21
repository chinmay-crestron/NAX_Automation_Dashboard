"""
performance_data.py
───────────────────
Reads C:\\nax-image-server\\document.csv and provides aggregated performance
counts for the dashboard.

CSV row format (comma-separated):
  timestamp, version, test_type, ip, result, device_name[, extra...]

Test type normalisation:
  FirmwareUpgradeDowngrade* → Firmware Upgrade/Downgrade
  Network_O / Network_Outage → Network Outage
  Reboot*                    → Reboot
  PowerCycle                 → PowerCycle
"""

import os
from typing import Dict, List, Optional

CSV_PATH = r"C:\nax-image-server\document.csv"

# ── Test-type normalisation map ───────────────────────────────────────────────

CANONICAL_TYPES = {
    "PowerCycle":   "PowerCycle",
    "Network_O":    "Network Outage",
    "Network_Outage": "Network Outage",
    "Reboot":       "Reboot",
}

# Everything starting with "FirmwareUpgradeDowngrade" or "Reboot_" also maps
def _normalise_test_type(raw: str) -> str:
    if raw in CANONICAL_TYPES:
        return CANONICAL_TYPES[raw]
    if raw.startswith("FirmwareUpgradeDowngrade"):
        return "Firmware Upgrade/Downgrade"
    if raw.startswith("Reboot"):
        return "Reboot"
    return raw  # unknown — keep as-is


# ── Ordered list for display ──────────────────────────────────────────────────

ALL_TEST_TYPES = ["PowerCycle", "Network Outage", "Reboot", "Firmware Upgrade/Downgrade"]


# ── Raw row parser ────────────────────────────────────────────────────────────

def _parse_rows() -> List[dict]:
    """
    Parse every row of the CSV into a list of dicts:
      { timestamp, version, test_type, ip, result, device_name }
    """
    rows = []
    if not os.path.exists(CSV_PATH):
        return rows

    with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 6:
                continue
            rows.append({
                "timestamp":   parts[0],
                "version":     parts[1],
                "test_type":   _normalise_test_type(parts[2]),
                "ip":          parts[3],
                "result":      parts[4],
                "device_name": parts[5],
            })
    return rows


# ── Public API ────────────────────────────────────────────────────────────────

def load_performance_data() -> List[dict]:
    """Return all rows with normalised test types."""
    return _parse_rows()


def get_available_devices(rows: List[dict]) -> List[str]:
    """Return sorted unique device names present in data."""
    return sorted({r["device_name"] for r in rows})


def get_versions_for_device(rows: List[dict], device_name: str) -> List[str]:
    """Return unique firmware versions for a device, latest (highest) first."""
    return sorted({r["version"] for r in rows if r["device_name"] == device_name}, reverse=True)


def get_ips_for_device(rows: List[dict], device_name: str) -> List[str]:
    """Return sorted unique IPs for a given device."""
    return sorted({r["ip"] for r in rows if r["device_name"] == device_name})


def get_test_types_for_device(rows: List[dict], device_name: str) -> List[str]:
    """Return sorted unique test types for a given device."""
    present = {r["test_type"] for r in rows if r["device_name"] == device_name}
    # Keep canonical order, then append any extras
    ordered = [t for t in ALL_TEST_TYPES if t in present]
    extras  = sorted(present - set(ALL_TEST_TYPES))
    return ordered + extras


def compute_counts(
    rows: List[dict],
    device_name: str,
    versions: Optional[List[str]] = None,
    ips: Optional[List[str]] = None,
    test_types: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    Filter rows by device_name, versions, ips, test_types and return
    a dict mapping test_type → count.
    """
    filtered = [r for r in rows if r["device_name"] == device_name]

    if versions:
        filtered = [r for r in filtered if r["version"] in versions]
    if ips:
        filtered = [r for r in filtered if r["ip"] in ips]
    if test_types:
        filtered = [r for r in filtered if r["test_type"] in test_types]

    counts: Dict[str, int] = {}
    for r in filtered:
        t = r["test_type"]
        counts[t] = counts.get(t, 0) + 1

    # Ensure all canonical types appear (even with 0)
    active_types = test_types if test_types else ALL_TEST_TYPES
    for t in active_types:
        counts.setdefault(t, 0)

    return counts


def get_total_device_count(
    rows: List[dict],
    device_name: str,
    versions: Optional[List[str]] = None,
    ips: Optional[List[str]] = None,
    test_types: Optional[List[str]] = None,
) -> int:
    """Return count of unique IPs matching the filters."""
    filtered = [r for r in rows if r["device_name"] == device_name]
    if versions:
        filtered = [r for r in filtered if r["version"] in versions]
    if ips:
        filtered = [r for r in filtered if r["ip"] in ips]
    if test_types:
        filtered = [r for r in filtered if r["test_type"] in test_types]
    return len({r["ip"] for r in filtered})

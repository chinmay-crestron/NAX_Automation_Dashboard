"""
Longevity data helpers
======================
Loads the device-health CSV produced by Longevity/backend/main_nax.py and
maps device IPs to friendly device names using the Longevity_devices section
of Nax_Devices.json.

CSV layout (see nax_config.LONGEVITY_CSV_COLUMNS):
    Timestamp,IP,Model,Uptime (Days),RAM Usage (%),User CPU (%),System CPU (%),
    Nice CPU (%),Idle CPU (%),IO CPU (%),IRQ CPU (%),SIRQ CPU (%)
"""

import json
import os

import pandas as pd

from nax_config import JSON_PATH, LONGEVITY_CSV_PATH, LONGEVITY_CSV_COLUMNS

CSV_PATH = LONGEVITY_CSV_PATH
CSV_COLUMNS = LONGEVITY_CSV_COLUMNS

ALL_DEVICES_LABEL = "All Devices"

NUMERIC_COLUMNS = [
    "Uptime (Days)",
    "RAM Usage (%)",
    "User CPU (%)",
    "System CPU (%)",
    "Nice CPU (%)",
    "Idle CPU (%)",
    "IO CPU (%)",
    "IRQ CPU (%)",
    "SIRQ CPU (%)",
]

CPU_BREAKDOWN_COLUMNS = [
    "User CPU (%)",
    "System CPU (%)",
    "Nice CPU (%)",
    "IO CPU (%)",
    "IRQ CPU (%)",
    "SIRQ CPU (%)",
]

_SHORT_DATE_RE = r"^\d{1,2}-\d{1,2}$"


# ── Device name lookup ────────────────────────────────────────────────────────

def load_longevity_device_map(json_path: str = JSON_PATH) -> dict:
    """Return {device_ip: device_name} for every non-empty Longevity device IP."""
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}

    ip_to_name = {}
    for model_name, devices in (data.get("Longevity_devices") or {}).items():
        if not isinstance(devices, dict):
            continue
        for device_id, cfg in devices.items():
            if not isinstance(cfg, dict):
                continue
            ip = str(cfg.get("device_ip", "")).strip()
            if not ip:
                continue
            name = str(cfg.get("device_name", "")).strip() or str(model_name).strip()
            ip_to_name[ip] = name or ip
    return ip_to_name


# ── CSV loading ───────────────────────────────────────────────────────────────

def _has_header(csv_path: str) -> bool:
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()
    except OSError:
        return False
    return first_line.strip().lower().startswith("timestamp")


def _parse_dates(raw: pd.Series) -> pd.Series:
    """Parse the CSV date column. Supports 'MM-DD' and full date strings."""
    text = raw.astype(str).str.strip()
    parsed = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")

    today = pd.Timestamp.today()
    short_mask = text.str.match(_SHORT_DATE_RE, na=False)

    if short_mask.any():
        short = pd.to_datetime(
            text[short_mask] + f"-{today.year}", format="%m-%d-%Y", errors="coerce"
        )
        # Dates in the future belong to the previous year (year rollover).
        rolled = short > (today + pd.Timedelta(days=1))
        short.loc[rolled] = short.loc[rolled] - pd.DateOffset(years=1)
        parsed.loc[short_mask] = short

    if (~short_mask).any():
        parsed.loc[~short_mask] = pd.to_datetime(
            text[~short_mask], errors="coerce", format="mixed"
        )

    return parsed


def load_longevity_data(csv_path: str = CSV_PATH) -> pd.DataFrame:
    """Read the event CSV into a cleaned DataFrame.

    Adds: Date (datetime), Date Label (str), Device (friendly name),
    CPU Busy (%), Record (per-device sequence index).
    Returns an empty DataFrame when the CSV is missing or unreadable.
    """
    empty = pd.DataFrame(columns=CSV_COLUMNS + ["Date", "Date Label", "Device", "CPU Busy (%)"])

    if not csv_path or not os.path.exists(csv_path):
        return empty

    try:
        if _has_header(csv_path):
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        else:
            df = pd.read_csv(csv_path, names=CSV_COLUMNS, encoding="utf-8-sig")
    except (OSError, ValueError, pd.errors.ParserError):
        return empty

    if df.empty:
        return empty

    # Normalise columns to the expected set.
    df = df.rename(columns=lambda c: str(c).strip())
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[CSV_COLUMNS].copy()

    df["IP"] = df["IP"].astype(str).str.strip()
    df["Model"] = df["Model"].astype(str).str.strip()
    df = df[df["IP"].ne("") & df["IP"].ne("nan")]

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Date"] = _parse_dates(df["Timestamp"])
    df = df.dropna(subset=["Date"])
    if df.empty:
        return empty

    df["Date Label"] = df["Date"].dt.strftime("%d %b")

    # Friendly device name: JSON config first, CSV model next, IP last.
    ip_to_name = load_longevity_device_map()
    csv_model = (
        df[df["Model"].ne("") & df["Model"].str.lower().ne("unknown")]
        .groupby("IP")["Model"]
        .last()
        .to_dict()
    )

    def _device_name(ip):
        return ip_to_name.get(ip) or csv_model.get(ip) or ip

    df["Device"] = df["IP"].map(_device_name)

    idle = df["Idle CPU (%)"]
    df["CPU Busy (%)"] = (100 - idle).clip(lower=0, upper=100)

    df = df.sort_values(["Date", "IP"]).reset_index(drop=True)
    df["Record"] = df.groupby("IP").cumcount() + 1
    return df


# ── Selection helpers ─────────────────────────────────────────────────────────

def build_device_options(df: pd.DataFrame) -> list:
    """Return [(label, ip)] for every device present in the data.

    Labels use the device name; the IP is appended only when a name is shared
    by more than one device so entries stay unambiguous.
    """
    if df.empty:
        return []

    pairs = (
        df[["IP", "Device"]]
        .drop_duplicates()
        .sort_values(["Device", "IP"])
        .to_records(index=False)
    )

    name_counts = {}
    for _, name in pairs:
        name_counts[name] = name_counts.get(name, 0) + 1

    options = []
    for ip, name in pairs:
        label = f"{name} ({ip})" if name_counts.get(name, 0) > 1 else str(name)
        options.append((label, str(ip)))
    return options


def filter_by_days(df: pd.DataFrame, days: int | None) -> pd.DataFrame:
    """Keep only rows from the latest `days` distinct dates. None = keep all."""
    if df.empty or not days:
        return df
    latest_dates = df["Date"].drop_duplicates().sort_values().tail(days)
    return df[df["Date"].isin(latest_dates)].copy()


def latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent record per device."""
    if df.empty:
        return df
    snapshot = (
        df.sort_values("Date")
        .groupby("IP", as_index=False)
        .tail(1)
        .sort_values("Device")
        .reset_index(drop=True)
    )
    return snapshot


def cpu_breakdown_long(df: pd.DataFrame) -> pd.DataFrame:
    """Melt CPU columns into long form for a multi-series chart."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Date Label", "Metric", "Value"])
    melted = df.melt(
        id_vars=["Date", "Date Label"],
        value_vars=CPU_BREAKDOWN_COLUMNS,
        var_name="Metric",
        value_name="Value",
    ).dropna(subset=["Value"])
    melted["Metric"] = melted["Metric"].str.replace(r"\s*CPU \(%\)$", "", regex=True)
    return melted

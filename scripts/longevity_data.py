"""
Longevity data helpers
======================
Loads the device-health CSV produced by Longevity/backend/main_nax.py and
groups records per Longevity device (Nax_Devices.json device ID), so a device
keeps a single history even when its IP changes.

CSV layout (see nax_config.LONGEVITY_CSV_COLUMNS):
    Timestamp,IP,Model,Uptime (Days),RAM Usage (%),User CPU (%),System CPU (%),
    Nice CPU (%),Idle CPU (%),IO CPU (%),IRQ CPU (%),SIRQ CPU (%),Device ID

Device resolution per row: saved Device ID -> current IP in the JSON ->
model reported by that IP (first device of the matching model section) ->
the IP itself.
"""

import json
import os
import re

import pandas as pd

from nax_config import JSON_PATH, LONGEVITY_CSV_PATH, LONGEVITY_CSV_COLUMNS

CSV_PATH = LONGEVITY_CSV_PATH
CSV_COLUMNS = LONGEVITY_CSV_COLUMNS

DEFAULT_FAMILY = "DM-NAX-8ZSA"

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

_SHORT_DATE_RE = r"^\d{1,2}-\d{1,2}$"
_ORPHAN_PREFIX = "ip:"


def _natural_key(text) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(text))]


def _is_edge(family: str) -> bool:
    return "edge" in family.lower()


def _valid_model(model) -> bool:
    text = str(model).strip()
    return bool(text) and text.lower() not in ("unknown", "nan", "none")


# ── Device config ───── ────────────────────────────────────────────────────────

def load_longevity_config(json_path: str = JSON_PATH) -> list:
    """Ordered [{'key', 'family', 'device_id', 'ip'}] for every Longevity device.

    'key' matches the Device ID written by main_nax.py ("<family>/<device id>").
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []

    devices = []
    for family, entries in (data.get("Longevity_devices") or {}).items():
        if not isinstance(entries, dict):
            continue
        device_ids = sorted((k for k, v in entries.items() if isinstance(v, dict)), key=_natural_key)
        for device_id in device_ids:
            devices.append({
                "key": f"{family}/{device_id}",
                "family": str(family),
                "device_id": str(device_id),
                "ip": str(entries[device_id].get("device_ip", "")).strip(),
            })
    return devices


def _family_for_model(model: str, families: list) -> str:
    """Non-edge model section matching a reported model, e.g. DM-NAX-4ZSA-50 -> DM-NAX-4ZSA."""
    model = str(model).strip().upper()
    for family in sorted(families, key=len, reverse=True):
        if _is_edge(family):
            continue
        fam = family.upper()
        if model == fam or model.startswith(fam + "-"):
            return family
    return ""


def _assign_device_keys(df: pd.DataFrame, config: list) -> pd.Series:
    families = list(dict.fromkeys(d["family"] for d in config))
    ip_to_key = {d["ip"]: d["key"] for d in config if d["ip"]}
    first_key = {}
    for d in config:
        first_key.setdefault(d["family"], d["key"])
    ip_model = df[df["Model"].map(_valid_model)].groupby("IP")["Model"].last().to_dict()

    def _key(saved: str, ip: str) -> str:
        if saved:
            return saved
        if ip in ip_to_key:
            return ip_to_key[ip]
        family = _family_for_model(ip_model.get(ip, ""), families)
        if family:
            return first_key[family]
        return _ORPHAN_PREFIX + ip

    saved_ids = df["Device ID"].fillna("").astype(str).str.strip().replace("nan", "")
    return pd.Series([_key(s, ip) for s, ip in zip(saved_ids, df["IP"])], index=df.index)


def _device_labels(df: pd.DataFrame, config: list) -> tuple[dict, dict]:
    """Return ({key: label}, {key: sort order}).

    Model sections: "DM-NAX-8ZSA", then "DM-NAX-8ZSA 2", "... 3" for extra device IDs.
    Edge devices: model reported by the device, with the IP only when the model repeats.
    """
    families = list(dict.fromkeys(d["family"] for d in config))
    config_ip = {d["key"]: d["ip"] for d in config}
    keys = list(df["Device Key"].unique())

    ordered = df.sort_values("Date")
    key_model = ordered[ordered["Model"].map(_valid_model)].groupby("Device Key")["Model"].last().to_dict()
    key_ip = ordered.groupby("Device Key")["IP"].last().to_dict()

    # Device IDs saved in the CSV but since removed from the JSON go after the configured ones.
    family_members = {f: [d["key"] for d in config if d["family"] == f] for f in families}
    for key in sorted(keys, key=_natural_key):
        if key.startswith(_ORPHAN_PREFIX):
            continue
        family = key.split("/", 1)[0]
        if family not in families:
            families.append(family)
        members = family_members.setdefault(family, [])
        if key not in members:
            members.append(key)

    labels, sort_keys, pooled = {}, {}, {}
    for key in keys:
        if key.startswith(_ORPHAN_PREFIX):
            family, rank = "", len(families)
        else:
            family = key.split("/", 1)[0]
            rank = families.index(family)

        if family and not _is_edge(family):
            pos = family_members[family].index(key) + 1
            labels[key] = family if pos == 1 else f"{family} {pos}"
            sort_keys[key] = (rank, [pos])
        else:
            fallback = key.split("/", 1)[1] if family else key[len(_ORPHAN_PREFIX):]
            base = key_model.get(key) or fallback
            pooled.setdefault(base, []).append(key)
            labels[key] = base
            sort_keys[key] = (rank, _natural_key(base))

    for base, members in pooled.items():
        if len(members) > 1:
            for key in members:
                ip = config_ip.get(key) or key_ip.get(key, "")
                labels[key] = f"{base} ({ip})"
                sort_keys[key] = (sort_keys[key][0], _natural_key(labels[key]))

    order = {key: i for i, key in enumerate(sorted(keys, key=lambda k: sort_keys[k]))}
    return labels, order


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

    Adds: Date (datetime), Date Label (str), Device Key (device identity),
    Device (display label), Device Order, CPU Busy (%), Record (per-device index).
    Returns an empty DataFrame when the CSV is missing or unreadable.
    """
    empty = pd.DataFrame(columns=CSV_COLUMNS + [
        "Date", "Date Label", "Device Key", "Device", "Device Order", "CPU Busy (%)",
    ])

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

    config = load_longevity_config()
    df["Device Key"] = _assign_device_keys(df, config)
    labels, order = _device_labels(df, config)
    df["Device"] = df["Device Key"].map(labels)
    df["Device Order"] = df["Device Key"].map(order)

    idle = df["Idle CPU (%)"]
    df["CPU Busy (%)"] = (100 - idle).clip(lower=0, upper=100)

    df = df.sort_values(["Date", "Device Order", "IP"]).reset_index(drop=True)
    df["Record"] = df.groupby("Device Key").cumcount() + 1
    return df


# ── Selection helpers ─────────────────────────────────────────────────────────

def build_device_options(df: pd.DataFrame) -> list:
    """Return [(label, device key)] for every device present in the data, in display order."""
    if df.empty:
        return []
    devices = (
        df[["Device Key", "Device", "Device Order"]]
        .drop_duplicates("Device Key")
        .sort_values("Device Order")
    )
    return [(str(label), str(key)) for key, label in zip(devices["Device Key"], devices["Device"])]


def default_device_index(options: list) -> int:
    """Index of the first DM-NAX-8ZSA device, else 0."""
    for i, (_, key) in enumerate(options):
        if key.split("/", 1)[0] == DEFAULT_FAMILY:
            return i
    return 0


def filter_by_days(df: pd.DataFrame, days: int | None) -> pd.DataFrame:
    """Keep only rows from the latest `days` distinct dates. None = keep all."""
    if df.empty or not days:
        return df
    latest_dates = df["Date"].drop_duplicates().sort_values().tail(days)
    return df[df["Date"].isin(latest_dates)].copy()


def latest_model(df: pd.DataFrame) -> str:
    """Most recent model the device reported, ignoring failed collections."""
    models = df.loc[df["Model"].map(_valid_model), "Model"]
    return str(models.iloc[-1]) if not models.empty else "Unknown"

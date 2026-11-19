"""Shared configuration for NAX dashboard pages."""

import os

def resolve_json_path():
    base_dir = os.path.dirname(__file__)
    preferred_path = r"C:\NAX-FRAMEWORK-U20\DM_NAX\src\TestData\Nax_Devices.json"
    env_path = os.getenv("NAX_JSON_PATH")
    local_path = os.path.join(base_dir, "Nax_Devices.json")
    legacy_path = os.path.join(base_dir, "..", "..", "TestData", "Nax_Devices.json")

    for candidate in [env_path, preferred_path, local_path, legacy_path]:
        if candidate and os.path.exists(candidate):
            return os.path.normpath(candidate)

    raise FileNotFoundError(
        "Nax_Devices.json not found. Checked: "
        f"{os.path.normpath(preferred_path)}, {os.path.normpath(local_path)} "
        f"and {os.path.normpath(legacy_path)}. "
        "Optionally set NAX_JSON_PATH to an absolute file path."
    )


JSON_PATH = resolve_json_path()


def resolve_longevity_csv_path():
    """Locate the Longevity device-health CSV written by the backend collector.

    Priority: NAX_LONGEVITY_CSV env var -> shared collector path -> repo copy.
    Returns the preferred path even when missing so the UI can report it.
    """
    base_dir = os.path.dirname(__file__)
    env_path = os.getenv("NAX_LONGEVITY_CSV")
    preferred_path = r"C:\runData_BTIO\event.csv"
    local_path = os.path.join(base_dir, "Longevity", "runData_BTIO", "event.csv")

    for candidate in [env_path, preferred_path, local_path]:
        if candidate and os.path.exists(candidate):
            return os.path.normpath(candidate)

    return os.path.normpath(preferred_path)


LONGEVITY_CSV_PATH = resolve_longevity_csv_path()

# Column order of the Longevity event CSV (kept in sync with
# Longevity/backend/main_nax.py)
LONGEVITY_CSV_COLUMNS = [
    "Timestamp",
    "IP",
    "Model",
    "Uptime (Days)",
    "RAM Usage (%)",
    "User CPU (%)",
    "System CPU (%)",
    "Nice CPU (%)",
    "Idle CPU (%)",
    "IO CPU (%)",
    "IRQ CPU (%)",
    "SIRQ CPU (%)",
    "Device ID",
]

SVN_URL = "svn://linux2/subversion/QE/Enterprise Software Automation/branches/NAX_u20"
SVN_USER = os.getenv("NAX_SVN_USER", "chinmay.naik")
SVN_PASS = os.getenv("NAX_SVN_PASS", "chinmay.naik031728")
SVN_BIN = os.getenv("NAX_SVN_BIN")

# Ordered mapping of JSON section key -> display name
DEVICE_CATEGORIES = {
    "Regression_devices":  "Regression Devices",
    "Performance_devices": "Performance Devices",
    "Longevity_devices":   "Longevity Devices",
    "Sanity_devices":      "Sanity Devices",
}

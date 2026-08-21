"""Shared configuration for NAX dashboard pages."""

import os

def resolve_json_path():
    base_dir = os.path.dirname(__file__)
    preferred_path = r"C:\NAX-FRAMEWORK\DM_NAX\src\TestData\Nax_Devices.json"
    env_path = os.getenv("NAX_JSON_PATH")
    local_path = os.path.join(base_dir, "Nax_Devices.json")
    legacy_path = os.path.join(base_dir, "..", "..", "TestData", "Nax_Devices.json")

    for candidate in [preferred_path, env_path, local_path, legacy_path]:
        if candidate and os.path.exists(candidate):
            return os.path.normpath(candidate)

    raise FileNotFoundError(
        "Nax_Devices.json not found. Checked: "
        f"{os.path.normpath(preferred_path)}, {os.path.normpath(local_path)} "
        f"and {os.path.normpath(legacy_path)}. "
        "Optionally set NAX_JSON_PATH to an absolute file path."
    )


JSON_PATH = resolve_json_path()

SVN_URL = "svn://linux2/subversion/QE/Enterprise Software Automation/branches/NAX_u16"
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

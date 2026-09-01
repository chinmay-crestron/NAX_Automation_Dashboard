"""
regression_paths.py
───────────────────
Configuration for regression log shared drive paths.

Structure:
    REGRESSION_LOG_PATHS[device] = r"\\server\share\path"

These are UNC paths to shared network folders containing regression logs.
Update the paths as needed for each device.
"""

# Base path for the regression logs share
REGRESSION_BASE = r"\\nax-jenkins\nax_logs\Regression"

REGRESSION_LOG_PATHS = {
    "DM-NAX-8ZSA":   rf"{REGRESSION_BASE}\8ZSA",
    "DM-NAX-4ZSA":   rf"{REGRESSION_BASE}\4ZSA",
    "DM-NAX-4ZSP":   rf"{REGRESSION_BASE}\4ZSP",
    "DM-NAX-16AIN":  rf"{REGRESSION_BASE}\16AIN",
    "DM-NAX-AMP300": rf"{REGRESSION_BASE}\AMP300",
    "Edge-Devices":   rf"{REGRESSION_BASE}\Edge-Devices",
    "Saros":          rf"{REGRESSION_BASE}\Saros",
}


def get_regression_log_path(device: str) -> str:
    """Return the UNC log path for a device, or '' if not configured."""
    return REGRESSION_LOG_PATHS.get(device, "")


def get_log_url(device: str) -> str:
    """
    Convert a UNC path to a file:/// URL that can be opened in a browser tab.
    e.g. \\\\server\\share → file://///server/share
    """
    unc = get_regression_log_path(device)
    if not unc:
        return ""
    # Convert backslashes to forward slashes for URL
    return "file:///" + unc.replace("\\", "/")

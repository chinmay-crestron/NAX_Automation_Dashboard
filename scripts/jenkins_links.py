"""
jenkins_links.py
────────────────
Central configuration file for Jenkins pipeline URLs used in the
NAX Automation Dashboard.

Structure:
    JENKINS_LINKS[section][device][job] = "URL"

Leave a URL as an empty string "" — it will appear as a disabled button
on the dashboard until you fill it in.
"""

JENKINS_LINKS = {
    # ── Performance Execution ─────────────────────────────────────────────────
    "performance_execution": {
        "DM-NAX-8ZSA": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
        "DM-NAX-4ZSA": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
        "DM-NAX-4ZSP": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
        "DM-NAX-16AIN": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
        "DM-NAX-AMP300": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
        "Edge-Devices": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
        "Saros": {
            "Powercycle":                 "",
            "Network Outage":             "",
            "Reboot":                     "",
            "Firmware Upgrade/Downgrade": "",
        },
    },
}

# ── Helper ────────────────────────────────────────────────────────────────────

def get_jenkins_url(section: str, device: str, job: str) -> str:
    """Return the Jenkins URL for a given section/device/job, or '' if not set."""
    return JENKINS_LINKS.get(section, {}).get(device, {}).get(job, "")

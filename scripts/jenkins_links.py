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
            "Powercycle":                 "http://nax-jenkins:8080/job/Performance/job/DM-NAX-8ZSA/job/Powercycle/",
            "Network Outage":             "http://nax-jenkins:8080/job/Performance/job/DM-NAX-8ZSA/job/Network_Outage/",
            "Reboot":                     "http://nax-jenkins:8080/job/Performance/job/DM-NAX-8ZSA/job/Reboot/",
            "Firmware Upgrade/Downgrade": "http://nax-jenkins:8080/job/Performance/job/DM-NAX-8ZSA/job/Firmware_Upgrade_Downgrade/",
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

    # ── Regression Execution ──────────────────────────────────────────────────
    "regression_execution": {
        "DM-NAX-8ZSA": {
            "Regression": "http://nax-jenkins:8080/job/8ZSA_Pipeline/",
        },
        "DM-NAX-4ZSA": {
            "Regression": "http://nax-jenkins:8080/job/4ZSA_Pipeline/",
        },
        "DM-NAX-4ZSP": {
            "Regression": "http://nax-jenkins:8080/job/4ZSP_Pipeline/",
        },
        "DM-NAX-16AIN": {
            "Regression": "http://nax-jenkins:8080/job/16AIN_Pipeline/",
        },
        "DM-NAX-AMP300": {
            "Regression": "",
        },
        "Edge-Devices": {
            "Regression": "",
        },
        "Saros": {
            "Regression": "",
        },
    },
}

# ── Helper ────────────────────────────────────────────────────────────────────

def get_jenkins_url(section: str, device: str, job: str) -> str:
    """Return the Jenkins URL for a given section/device/job, or '' if not set."""
    return JENKINS_LINKS.get(section, {}).get(device, {}).get(job, "")

"""
NAX Longevity — Device Health Collector
=======================================
Collects health metrics (version, model, uptime, memory, CPU load, reboot
status) over SSH from every Longevity device configured in Nax_Devices.json,
appends a row per device to the event CSV consumed by the dashboard
(Longevity page) and emails an HTML summary report.

Device selection:
    Every entry under "Longevity_devices" in Nax_Devices.json with a
    non-empty "device_ip" is monitored (device names are ignored — the model
    name is read from the device itself over SSH).

CSV layout (appended, header written once):
    Timestamp,IP,Model,Uptime (Days),RAM Usage (%),User CPU (%),System CPU (%),
    Nice CPU (%),Idle CPU (%),IO CPU (%),IRQ CPU (%),SIRQ CPU (%),Device ID

    Device ID is "<model section>/<device id>" from Nax_Devices.json so the
    dashboard keeps one history per device even when its IP changes. Older
    files without that column are upgraded in place.

Usage (Jenkins scheduled job):
    python main_nax.py --recipients "a@crestron.com,b@crestron.com"

    Optional:
      --json           Path to Nax_Devices.json
      --csv            Path to the event CSV (default C:\\runData_BTIO\\event.csv)
      --username       Override the SSH username for every device
      --password       Override the SSH password for every device
      --subject        Email subject
      --dashboard-url  Link shown in the email body
      --no-mail        Collect data only, skip the email
      --timeout        SSH timeout in seconds (default 10)

SMTP settings mirror the framework's EmailUtil.java and can be overridden with
the NAX_SMTP_HOST / NAX_SMTP_PORT / NAX_SMTP_USER / NAX_SMTP_PASSWORD
environment variables (recommended for Jenkins credential binding).
"""

import argparse
import json
import os
import re
import smtplib
import sys
from csv import reader, writer
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ssh  # noqa: E402

# ── Configuration ─────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "Timestamp", "IP", "Model", "Uptime (Days)", "RAM Usage (%)",
    "User CPU (%)", "System CPU (%)", "Nice CPU (%)", "Idle CPU (%)",
    "IO CPU (%)", "IRQ CPU (%)", "SIRQ CPU (%)", "Device ID",
]

DEFAULT_CSV_PATH = os.getenv("NAX_LONGEVITY_CSV", r"C:\runData_BTIO\event.csv")
DEFAULT_DASHBOARD_URL = os.getenv(
    "NAX_LONGEVITY_DASHBOARD_URL", "http://172.18.88.51:8501/longevity"
)
DEFAULT_SUBJECT = "NAX Edge Devices Longevity Health Status"

DEFAULT_SSH_USER = "admin"
DEFAULT_SSH_PASSWORD = "admin123"
SSH_PORT = 22

SMTP_HOST = os.getenv("NAX_SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("NAX_SMTP_PORT", "587"))
SMTP_USER = os.getenv("NAX_SMTP_USER", "qeauto@crestron.com")
# Prefer supplying the password through NAX_SMTP_PASSWORD (Jenkins credential
# binding) instead of relying on the framework default below.
SMTP_PASSWORD = os.getenv("NAX_SMTP_PASSWORD", "uzxzdeGFQPy#Q9C")
SENDER_NAME = "NAX Automation"

NA = "N/A"
LOGIN_FAILED = "Login Failed"


# ── JSON / device discovery ───────────────────────────────────────────────────

def resolve_json_path(explicit_path=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        explicit_path,
        os.getenv("NAX_JSON_PATH"),
        r"C:\NAX-FRAMEWORK-U20\DM_NAX\src\TestData\Nax_Devices.json",
        os.path.join(base_dir, "..", "..", "Nax_Devices.json"),
        os.path.join(base_dir, "..", "..", "..", "TestData", "Nax_Devices.json"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.normpath(candidate)
    raise FileNotFoundError(
        "Nax_Devices.json not found. Pass --json <path> or set NAX_JSON_PATH."
    )


def load_longevity_devices(json_path):
    """Return [{'ip','username','password','config_id'}] for every non-empty
    device_ip found under Longevity_devices."""
    with open(json_path, "r") as f:
        data = json.load(f)

    devices = []
    seen = set()
    for model_name, entries in (data.get("Longevity_devices") or {}).items():
        if not isinstance(entries, dict):
            continue
        for device_id, cfg in entries.items():
            if not isinstance(cfg, dict):
                continue
            ip = str(cfg.get("device_ip", "")).strip()
            if not ip or ip in seen:
                continue
            seen.add(ip)
            devices.append({
                "ip": ip,
                "username": str(cfg.get("device_username", "")).strip() or DEFAULT_SSH_USER,
                "password": str(cfg.get("device_password", "")).strip() or DEFAULT_SSH_PASSWORD,
                "config_id": f"{model_name}/{device_id}",
            })
    return devices


# ── SSH helpers / parsers ─────────────────────────────────────────────────────

def run_command(ip, username, password, command, timeout):
    output, error = ssh.ssh_command_BTIO(ip, SSH_PORT, username, password, command, timeout)
    if output is None:
        print(f"[{ip}] SSH error running '{command.strip()}': {error}")
        return ""
    return output


def parse_ram_percent(output):
    match = re.search(r"(\d+)\s+percent of memory in use", output or "")
    return match.group(1) if match else NA


def parse_cpu_percentages(output):
    """Return {usr, sys, nic, idle, io, irq, sirq} percentages as strings."""
    result = {k: NA for k in ("usr", "sys", "nic", "idle", "io", "irq", "sirq")}
    for line in (output or "").splitlines():
        if "CPU:" in line:
            matches = re.findall(r"([\d\.]+)%\s*(usr|sys|nic|idle|io|irq|sirq)", line)
            for value, key in matches:
                result[key] = value.split(".")[0]
            if matches:
                break
    return result


def parse_memory_used(output):
    """Extract 'Mem: 3277980K used' -> '3277980' (CPU Load column of the mail)."""
    for line in (output or "").splitlines():
        line = line.strip()
        if line.startswith("Mem:"):
            for part in line.split(","):
                part = part.strip()
                if "used" in part:
                    digits = re.sub(r"[^0-9]", "", part.split("K")[0])
                    if digits:
                        return digits
    return ""


def parse_uptime_days(output):
    for line in (output or "").splitlines():
        if "The system has been running for" in line:
            match = re.search(r"for\s+(\d+)\s+days", line)
            return match.group(1) if match else "0"
    return NA


def parse_version_and_model(output):
    """Parse 'DM-NAX-BTIO-1G [v1.0.0677.10017 ...]' -> (version, model)."""
    version = "Unknown"
    model = "Unknown"
    for line in (output or "").splitlines():
        line = line.strip()
        if re.match(r"^[A-Z0-9\-]+ \[.*", line):
            model = line.split(" [")[0].strip()
            version_match = re.search(r"\[(v[0-9][^\s\]]*)", line)
            if version_match:
                version = version_match.group(1)
            break
    return version, model


def parse_reboot_status(output):
    """Return the 'YYYY-MM-DD HH:MM:SS manual|poweron' line from nvramreboot."""
    for line in (output or "").splitlines():
        line = line.strip()
        if not line or line.lower() == "nvramreboot":
            continue
        if re.match(
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+[-+]\d{4})?\s+(manual|poweron)", line
        ):
            return line
    return ""


# ── Collection ────────────────────────────────────────────────────────────────

def collect_device_health(device, timeout):
    """Collect every metric for one device. Never raises."""
    ip = device["ip"]
    username = device["username"]
    password = device["password"]

    data = {
        "ip": ip,
        "config_id": device["config_id"],
        "version": "Unknown",
        "model": "Unknown",
        "uptime_days": NA,
        "uptime_display": LOGIN_FAILED,
        "memory": NA,
        "cpu_load": "",
        "reboot_status": "",
        "cpu": {k: NA for k in ("usr", "sys", "nic", "idle", "io", "irq", "sirq")},
        "reachable": False,
    }

    try:
        uptime_output = run_command(ip, username, password, "uptime", timeout)
        if not uptime_output.strip():
            print(f"[{ip}] Device not responding or login failed.")
            return data

        data["reachable"] = True

        uptime_days = parse_uptime_days(uptime_output)
        data["uptime_days"] = uptime_days
        data["uptime_display"] = f"{uptime_days} days" if uptime_days != NA else NA
        print(f"[{ip}] Uptime          : {data['uptime_display']}")

        ver_output = run_command(ip, username, password, "ver -v", timeout)
        data["version"], data["model"] = parse_version_and_model(ver_output)
        print(f"[{ip}] Model / Version : {data['model']} / {data['version']}")

        ram_output = run_command(ip, username, password, "ramfree", timeout)
        data["memory"] = parse_ram_percent(ram_output)
        print(f"[{ip}] RAM usage       : {data['memory']} percent")

        cpu_output = run_command(ip, username, password, "cpuload", timeout)
        data["cpu"] = parse_cpu_percentages(cpu_output)
        data["cpu_load"] = parse_memory_used(cpu_output)
        print(f"[{ip}] CPU             : {data['cpu']}")
        print(f"[{ip}] Memory used (K) : {data['cpu_load']}")

        reboot_output = run_command(ip, username, password, "nvramreboot", timeout)
        data["reboot_status"] = parse_reboot_status(reboot_output)
        print(f"[{ip}] Reboot status   : {data['reboot_status']}")

    except Exception as exc:  # noqa: BLE001 - one bad device must not stop the run
        print(f"[{ip}] Error collecting device health: {exc}")

    return data


# ── CSV output ────────────────────────────────────────────────────────────────

def ensure_csv_header(csv_path):
    """Create the CSV with the current header, or rewrite an older/missing header in place."""
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer(f).writerow(CSV_COLUMNS)
        return

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(reader(f))
    header = [c.strip() for c in rows[0]] if rows else []
    # Older collector versions appended a header line mid-file on every run; drop those.
    data_rows = [r for r in rows if r and r[0].lstrip("\ufeff").strip().lower() != "timestamp"]
    if header == CSV_COLUMNS and len(data_rows) == sum(1 for r in rows[1:] if r):
        return

    width = len(CSV_COLUMNS)
    tmp_path = csv_path + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        csv_writer = writer(f)
        csv_writer.writerow(CSV_COLUMNS)
        for row in data_rows:
            if row:
                csv_writer.writerow((row + [""] * width)[:width])
    os.replace(tmp_path, csv_path)
    print(f"Upgraded CSV header in {csv_path}")


def append_to_csv(csv_path, rows):
    """Append one row per device, making sure the file has the current header."""
    directory = os.path.dirname(os.path.abspath(csv_path))
    if directory:
        os.makedirs(directory, exist_ok=True)

    ensure_csv_header(csv_path)

    timestamp = datetime.now().strftime("%m-%d")

    with open(csv_path, "a", newline="", encoding="utf-8") as f_object:
        csv_writer = writer(f_object)
        for data in rows:
            cpu = data["cpu"]
            csv_writer.writerow([
                timestamp,
                data["ip"],
                data["model"],
                data["uptime_days"],
                data["memory"],
                cpu["usr"], cpu["sys"], cpu["nic"], cpu["idle"],
                cpu["io"], cpu["irq"], cpu["sirq"],
                data["config_id"],
            ])

    print(f"\nAppended {len(rows)} row(s) to {csv_path}")


# ── Email report ──────────────────────────────────────────────────────────────

def build_email_body(rows, dashboard_url):
    """HTML body mirroring the previous BTIO_commands.java report."""
    parts = [
        "<h2>Device Health Summary</h2>",
        "<p>To visualize the data, please click on the link: ",
        f'<a href="{dashboard_url}">{dashboard_url}</a></p>',
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse: collapse;"
        " font-family: Calibri, Arial, sans-serif; font-size: 13px;'>",
        "<tr><th>Device IP</th><th>Version</th><th>Model</th><th>Uptime</th>"
        "<th>Memory Usage</th><th>CPU Load</th><th>Reboot Status</th></tr>",
    ]

    for data in rows:
        login_failed = not data["reachable"]
        color = "red" if login_failed else "black"

        if login_failed:
            version = model = "Unknown"
            uptime = LOGIN_FAILED
            memory = cpu_load = "-"
            reboot = ""
        else:
            version = data["version"]
            model = data["model"]
            uptime = data["uptime_display"]
            memory = f"{data['memory']} Percent" if data["memory"] != NA else NA
            cpu_load = data["cpu_load"]
            reboot = data["reboot_status"]

        parts.append("<tr>")
        for cell in [data["ip"], version, model, uptime, memory, cpu_load, reboot]:
            parts.append(f"<td style='color:{color};'>{cell if cell is not None else ''}</td>")
        parts.append("</tr>")

    parts.append("</table>")
    parts.append(
        "<p style='font-family: Calibri, Arial, sans-serif; font-size: 12px; color:#666;'>"
        f"Generated on {datetime.now().strftime('%d %b %Y %H:%M:%S')}</p>"
    )
    return "".join(parts)


def parse_recipients(values):
    """Flatten repeated / comma / semicolon separated recipient arguments."""
    recipients = []
    for value in values or []:
        for item in re.split(r"[,;\s]+", str(value)):
            item = item.strip()
            if item and item not in recipients:
                recipients.append(item)
    return recipients


def send_email_report(recipients, subject, html_body):
    message = MIMEMultipart("alternative")
    message["Subject"] = f"{subject} | Execution Report"
    message["From"] = f"{SENDER_NAME} <{SMTP_USER}>"
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html"))

    print(f"Sending report to: {', '.join(recipients)}")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, recipients, message.as_string())
    print("Device report email sent successfully.")


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collect NAX Longevity device health, append to CSV and email the report."
    )
    parser.add_argument(
        "--recipients", action="append", default=None,
        help="Comma separated email recipients (can be repeated). "
             "Falls back to the NAX_LONGEVITY_MAIL_TO environment variable.",
    )
    parser.add_argument("--json", default=None, help="Path to Nax_Devices.json")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to the event CSV")
    parser.add_argument("--username", default=None, help="Override SSH username for all devices")
    parser.add_argument("--password", default=None, help="Override SSH password for all devices")
    parser.add_argument("--subject", default=DEFAULT_SUBJECT, help="Email subject")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL,
                        help="Dashboard link included in the email body")
    parser.add_argument("--timeout", type=int, default=10, help="SSH timeout in seconds")
    parser.add_argument("--no-mail", action="store_true", help="Skip sending the email report")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    json_path = resolve_json_path(args.json)
    print(f"Device config : {json_path}")

    devices = load_longevity_devices(json_path)
    if not devices:
        print("No Longevity devices with a non-empty device_ip were found. Nothing to do.")
        return 1

    if args.username:
        for device in devices:
            device["username"] = args.username
    if args.password:
        for device in devices:
            device["password"] = args.password

    print(f"Monitoring {len(devices)} device(s): {', '.join(d['ip'] for d in devices)}")

    rows = []
    for device in devices:
        print(f"\n--- Collecting {device['ip']} ({device['config_id']}) ---")
        rows.append(collect_device_health(device, args.timeout))

    append_to_csv(args.csv, rows)

    if args.no_mail:
        print("--no-mail supplied, skipping email report.")
        return 0

    recipients = parse_recipients(args.recipients or [os.getenv("NAX_LONGEVITY_MAIL_TO", "")])
    if not recipients:
        print("No recipients provided (--recipients / NAX_LONGEVITY_MAIL_TO). Skipping email.")
        return 0

    html_body = build_email_body(rows, args.dashboard_url)
    try:
        send_email_report(recipients, args.subject, html_body)
    except Exception as exc:  # noqa: BLE001 - collected data is already persisted
        print(f"Failed to send email: {exc}")
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())

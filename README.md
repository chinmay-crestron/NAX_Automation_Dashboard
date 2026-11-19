# NAX Automation Dashboard

Centralized Streamlit dashboard for NAX device configuration, health status,
performance, regression and longevity monitoring.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Same version used to build the original `.venv` (3.10.x recommended). |
| Git | To clone/update the repo. |
| Network access | To the NAX devices (SSH/22) and, for Longevity email, to `smtp.office365.com:587`. |
| `Nax_Devices.json` | Device config source of truth. Either use the path baked into `nax_config.py` (`C:\NAX-FRAMEWORK-U20\DM_NAX\src\TestData\Nax_Devices.json`) or point `NAX_JSON_PATH` at your copy (see §4). |

---

## 2. Clone the repo

```powershell
git clone <repo-url> C:\NAX_Automation_Dashboard
cd C:\NAX_Automation_Dashboard
```

---

## 3. Create the virtual environment & install dependencies

```powershell
# From the repo root
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1

# If script execution is blocked:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

python -m pip install --upgrade pip
pip install -r requirements.txt

# Only needed if you'll run scripts\_diag.py or any Playwright-based script
python -m playwright install chromium
```

`requirements.txt` now includes everything used across the app: Streamlit/pandas/altair
(dashboard + Longevity charts), matplotlib (legacy `Longevity/UI` scripts), paramiko
(SSH collection), selenium + webdriver-manager (firmware upgrade automation) and
playwright (diagnostic scripts). Nothing else needs to be installed manually.

---

## 4. Configure device data paths (only if different from defaults)

The app resolves these automatically, but you can override with environment
variables (set them **before** launching Streamlit, e.g. via PowerShell
`$env:NAME="value"` or Windows System Environment Variables so they persist):

| Variable | Purpose | Default |
|---|---|---|
| `NAX_JSON_PATH` | Path to `Nax_Devices.json` (takes priority over the default) | `C:\NAX-FRAMEWORK-U20\DM_NAX\src\TestData\Nax_Devices.json` (falls back to the repo's own `Nax_Devices.json`) |
| `NAX_LONGEVITY_CSV` | Path to the Longevity event CSV read by the dashboard | `C:\runData_BTIO\event.csv` |

If neither the preferred path nor the env var exists, the app falls back to the
copy checked into the repo (`Nax_Devices.json`, `Longevity/runData_BTIO/event.csv`).

---

## 5. Launch the dashboard

```powershell
cd C:\NAX_Automation_Dashboard
.\.venv\Scripts\Activate.ps1
streamlit run app.py --server.port 8501
```

Open `http://<server-ip>:8501` in a browser. Pages available: Home, Device
Config, Device Status, Performance, Regression, Longevity.

To run it as a persistent service on the server, wrap the same command in a
scheduled task / NSSM service / `pm2`, etc., so it restarts on reboot.

---

## 6. Longevity data collection (separate from the dashboard)

The dashboard's **Longevity** page only *reads* `event.csv`. Data is produced by
a separate collector script that you run periodically (e.g. via a scheduled
Jenkins job) on a machine that has SSH access to the devices:

```powershell
cd C:\NAX_Automation_Dashboard\Longevity\backend
python .\main_nax.py --recipients "chinmay.naik@crestron.com,other@crestron.com"
```

- Reads device IPs from `Longevity_devices` in `Nax_Devices.json` (any entry with
  a non-empty `device_ip`; add/remove devices there via the Device Config page).
- Appends one row per device to the CSV (`C:\runData_BTIO\event.csv` by default —
  make sure this matches `NAX_LONGEVITY_CSV` used by the dashboard, or use `--csv`).
- Emails an HTML health summary to `--recipients` (or `NAX_LONGEVITY_MAIL_TO`).

Useful flags: `--json <path>`, `--csv <path>`, `--username`/`--password`
(override SSH creds), `--timeout <sec>`, `--no-mail`, `--dashboard-url <url>`.

SMTP defaults mirror the Java framework (`smtp.office365.com:587`,
`qeauto@crestron.com`) and can be overridden with `NAX_SMTP_HOST`,
`NAX_SMTP_PORT`, `NAX_SMTP_USER`, `NAX_SMTP_PASSWORD` — set the password via a
Jenkins credential binding rather than hardcoding it.

`ssh.py` must stay in the same folder as `main_nax.py` — copy both files
together if you deploy the collector to a different location (e.g.
`C:\Monitoring\backend`).

---

## 7. Switching to a different framework branch

Device details come from `Nax_Devices.json` inside a local checkout of the NAX
framework SVN branch (currently `NAX_u20`, checked out at `C:\NAX-FRAMEWORK-U20`).
To move the dashboard to another branch (e.g. `NAX_u22`):

1. Check out the new branch locally, e.g.
   `svn checkout "svn://linux2/subversion/QE/Enterprise Software Automation/branches/NAX_u22" C:\NAX-FRAMEWORK-U22`
   and make sure its `DM_NAX\src\TestData\Nax_Devices.json` is up to date.
2. Update the path in these two places (search for `NAX-FRAMEWORK`):
   - `nax_config.py` → `preferred_path` in `resolve_json_path()` and `SVN_URL`
     (`SVN_URL` is shown in the UI; the commit itself goes to wherever the
     working copy of `Nax_Devices.json` points).
   - `Longevity/backend/main_nax.py` → the path in `resolve_json_path()`.
3. Update the paths in this README (§1 and §4).
4. Restart Streamlit. Every machine running the Longevity collector needs the
   updated `main_nax.py` (or the `NAX_JSON_PATH` variable / `--json` flag).

No code change is needed for a quick/temporary switch: set `NAX_JSON_PATH` to the
new file (it takes priority over the built-in default), e.g.
`$env:NAX_JSON_PATH="C:\NAX-FRAMEWORK-U22\DM_NAX\src\TestData\Nax_Devices.json"`,
or pass `--json <path>` to `main_nax.py`.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'paramiko'` (or any package) | Re-run `pip install -r requirements.txt` inside the activated venv. |
| `FileNotFoundError: Nax_Devices.json not found` | Set `NAX_JSON_PATH` to the correct absolute path. |
| Longevity page shows "No Longevity data available yet" | The collector (`Longevity/backend/main_nax.py`) hasn't run yet, or `NAX_LONGEVITY_CSV` on the dashboard machine doesn't match the CSV path used by the collector. |
| Longevity email fails to send | Check `NAX_SMTP_*` env vars / credentials and outbound access to `smtp.office365.com:587` from the machine running the collector. |
| Port 8501 already in use | Pass a different port: `streamlit run app.py --server.port <port>`. |

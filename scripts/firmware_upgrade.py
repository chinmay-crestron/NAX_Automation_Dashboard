"""
NAX Firmware Upgrade via Web UI (Selenium)
==========================================
Automates firmware upgrade for one or more NAX devices through the device Web UI.

XPaths sourced from:
  C:\\NAX-FRAMEWORK\\DM_NAX\\src\\TestData\\DeviceUIMap\\NAX.json
Flow sourced from:
  C:\\NAX-FRAMEWORK\\DM_NAX\\src\\TestScripts\\Devices_8ZSA\\Firmware_Update\\FW_004_Web_UI_Update.java

Usage (standalone):
    python scripts/firmware_upgrade.py ^
        --devices 172.30.2.147 172.30.2.148 ^
        --user admin --password admin123 ^
        --firmware C:\\path\\to\\firmware.puf ^
        [--headless]

Usage (from Dashboard):
    Import upgrade_device() and run it in a thread with a status callback.
"""

import argparse
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager


# ── XPaths ────────────────────────────────────────────────────────────────────

class XP:
    # Login page
    USERNAME_INPUT   = "//input[@id='cred_userid_inputtext']"
    PASSWORD_INPUT   = "//input[@id='cred_password_inputtext']"
    SIGN_IN_BUTTON   = "//button[@id='submitBtn']/span[@class='ui-button-text ui-c']"

    # Actions split-button dropdown chevron
    ACTIONS_BUTTON   = "//p-splitbutton//button[contains(@class,'p-splitbutton-menubutton')]"

    # Actions menu item
    UPDATE_FIRMWARE  = "//li[@id='updateFirmwareVersionAction']//a"

    # Firmware upload dialog
    BROWSE_BUTTON    = "//*[@id='fUplaod_DeviceManagement_Firmware_SelectFile']//span[contains(@class,'p-fileupload-choose')]"
    FILE_INPUT       = "//*[@id='fUplaod_DeviceManagement_Firmware_SelectFile']//input[@type='file']"
    LOAD_BUTTON      = "//button[contains(.,'Load')]"
    OK_BUTTON        = "//button[contains(.,'OK')]"

    # Status tab — firmware version verification
    STATUS_TAB       = "//li//span[contains(text(),'Status')]"
    DEVICE_ACCORDION = "//*[normalize-space(text())='Device']//preceding::span[contains(@class,'toggle-icon')][1]"
    FW_VERSION_VALUE = "//label[text()='Firmware Version']/parent::div/following-sibling::div"


# ── Status tracking ───────────────────────────────────────────────────────────

class UpgradeStatus(str, Enum):
    PENDING    = "Pending"
    LOGGING_IN = "Logging in"
    UPLOADING  = "Uploading"
    FLASHING   = "Flashing"
    REBOOTING  = "Rebooting"
    VERIFYING  = "Verifying"
    SUCCESS    = "Success"
    FAILED     = "Failed"


@dataclass
class DeviceResult:
    host:              str
    status:            UpgradeStatus = UpgradeStatus.PENDING
    message:           str           = ""
    fw_version_before: str           = ""
    fw_version_after:  str           = ""
    log:               List[str]     = field(default_factory=list)

    def update(self, status: UpgradeStatus, msg: str = ""):
        self.status  = status
        self.message = msg
        self.log.append(f"[{status.value}] {msg}" if msg else f"[{status.value}]")


# ── Driver factory ────────────────────────────────────────────────────────────

def _make_driver(headless: bool) -> webdriver.Chrome:
    opts = ChromeOptions()
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors=yes")
    opts.add_argument("--allow-running-insecure-content")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    if headless:
        opts.add_argument("--headless=new")
    service = ChromeService(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def _wait(driver: webdriver.Chrome, timeout: int = 20) -> WebDriverWait:
    return WebDriverWait(driver, timeout)


def _sleep_with_keepalive(driver: webdriver.Chrome, total_seconds: int, interval: int = 30):
    """
    Sleep for total_seconds, touching the browser every `interval` seconds
    so ChromeDriver does not go stale and crash during long idle waits.
    """
    elapsed = 0
    while elapsed < total_seconds:
        chunk = min(interval, total_seconds - elapsed)
        time.sleep(chunk)
        elapsed += chunk
        try:
            _ = driver.current_url  # keep-alive ping to ChromeDriver
        except Exception:
            pass  # browser may have navigated during flash — that is fine


# ── Helpers (mirrored from open_webui.py) ─────────────────────────────────────

def _fill_field(element, value: str):
    """Type character-by-character to trigger Angular change/validators."""
    from selenium.webdriver.common.keys import Keys
    element.click()
    time.sleep(0.2)
    element.send_keys(Keys.CONTROL + "a")
    element.send_keys(Keys.DELETE)
    time.sleep(0.1)
    for char in value:
        element.send_keys(char)
        time.sleep(0.04)


def _find_sign_in_button(driver: webdriver.Chrome):
    """Try multiple strategies to locate the Sign In / Submit button."""
    strategies = [
        (By.XPATH,        "//button[@id='submitBtn']/span[@class='ui-button-text ui-c']"),
        (By.XPATH,        "//button[@id='submitBtn']"),
        (By.XPATH,        "//button[contains(normalize-space(),'Sign In')]"),
        (By.XPATH,        "//button[contains(normalize-space(),'Sign in')]"),
        (By.XPATH,        "//button[contains(normalize-space(),'Login')]"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.XPATH,        "//input[@type='submit']"),
    ]
    for by, sel in strategies:
        try:
            btn = driver.find_element(by, sel)
            if btn.is_displayed():
                return btn
        except Exception:
            continue
    return None


# ── Login ─────────────────────────────────────────────────────────────────────

def _login(driver: webdriver.Chrome, host: str, user: str, password: str):
    """
    Navigate directly to https://<host>/userlogin.html and log in.
    Uses character-by-character typing to trigger Angular validators.
    """
    driver.get(f"https://{host}/userlogin.html")
    time.sleep(1.5)

    wait = _wait(driver, 20)

    # Locate fields by placeholder (robust against ID changes)
    user_el = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Username']"))
    )
    pass_el = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Password']"))
    )

    _fill_field(user_el, user)
    time.sleep(0.3)
    _fill_field(pass_el, password)
    time.sleep(0.3)

    btn = _find_sign_in_button(driver)
    if btn is None:
        raise RuntimeError("Sign In button not found on login page")

    # Wait until button is enabled (Angular validates after field input)
    _wait(driver, 15).until(lambda d: _find_sign_in_button(d) and _find_sign_in_button(d).is_enabled())
    btn = _find_sign_in_button(driver)
    btn.click()

    # Wait for login form to disappear — redirect to main app
    _wait(driver, 30).until(
        EC.invisibility_of_element_located((By.CSS_SELECTOR, "form#credentials"))
    )
    time.sleep(2)


# ── Firmware version reader ───────────────────────────────────────────────────

def _get_fw_version_ssh(host: str, user: str, password: str) -> str:
    """Read firmware version via SSH using the FLASHVERSION CLI command."""
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            host, port=22, username=user, password=password,
            timeout=10, look_for_keys=False, allow_agent=False,
        )
        _, stdout, _ = client.exec_command("FLASHVERSION")
        output = stdout.read().decode().strip()
        client.close()
        # Output: "Flash Version: 3.2.0102.23053" or "Flash Version: Unavailable"
        for line in output.splitlines():
            if "Flash Version:" in line:
                ver = line.split("Flash Version:")[-1].strip()
                return ver if ver.lower() != "unavailable" else "unavailable"
        return output or "unknown"
    except Exception as e:
        return f"unknown ({e})"


# ── Network helper ────────────────────────────────────────────────────────────

def _ping(host: str, timeout: int = 2) -> bool:
    """Return True if host responds to a ping."""
    param  = "-n" if sys.platform.startswith("win") else "-c"
    w_flag = ["-w", str(timeout * 1000)] if sys.platform.startswith("win") else ["-W", str(timeout)]
    try:
        return subprocess.run(
            ["ping", param, "1"] + w_flag + [host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except Exception:
        return False


# ── Core upgrade ──────────────────────────────────────────────────────────────

def upgrade_device(
    host:          str,
    user:          str,
    password:      str,
    firmware_path: str,
    headless:      bool = True,
    on_status:     Optional[Callable[[DeviceResult], None]] = None,
) -> DeviceResult:
    """
    Upgrade one NAX device via Web UI (Selenium/Chrome).

    Post-Load wait strategy:
      1. Initial 10-minute wait.
      2. Poll OK button every 2 min, up to 10 times.
      3. Click OK → wait 120 s.
      4. Ping every 30 s, up to 6 times.
      5. Re-login with up to 6 retries (30 s gap).
      6. Read firmware version → done.
    """
    result = DeviceResult(host=host)

    def notify(status: UpgradeStatus, msg: str = ""):
        result.update(status, msg)
        if on_status:
            on_status(result)

    fw_file = Path(firmware_path)
    if not fw_file.is_file():
        notify(UpgradeStatus.FAILED, f"Firmware file not found: {firmware_path}")
        return result

    driver = None
    try:
        driver = _make_driver(headless)

        # ── Step 1: Login ──────────────────────────────────────────────────
        notify(UpgradeStatus.LOGGING_IN, f"Logging in to {host}")
        _login(driver, host, user, password)

        # ── Step 2: Read current firmware version via SSH ────────────────
        result.fw_version_before = _get_fw_version_ssh(host, user, password)
        notify(UpgradeStatus.LOGGING_IN, f"Current FW: {result.fw_version_before}")

        # ── Step 3: Open Actions menu — retry 6×, 10 s gap ─────────────
        notify(UpgradeStatus.UPLOADING, "Opening Actions dropdown")
        actions_ok = False
        for attempt in range(1, 7):
            try:
                _wait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, XP.ACTIONS_BUTTON))
                ).click()
                _wait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, XP.UPDATE_FIRMWARE))
                )
                actions_ok = True
                break
            except Exception as e:
                notify(UpgradeStatus.UPLOADING, f"Actions attempt {attempt}/6 failed: {e}")
                if attempt < 6:
                    time.sleep(10)

        if not actions_ok:
            notify(UpgradeStatus.FAILED, "Could not open Actions menu after 6 attempts")
            return result

        # ── Step 4: Click Update Firmware ────────────────────────────────────
        time.sleep(2)
        _wait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, XP.UPDATE_FIRMWARE))
        ).click()

        # ── Step 5: Upload firmware file ──────────────────────────────────────
        time.sleep(2)
        notify(UpgradeStatus.UPLOADING, f"Selecting: {fw_file.name}")
        file_input = _wait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, XP.FILE_INPUT))
        )
        # Make hidden input visible so Selenium can interact with it
        driver.execute_script("arguments[0].style.display='block';", file_input)
        file_input.send_keys(str(fw_file))

        # ── Step 6: Click Load ───────────────────────────────────────
        time.sleep(2)
        _wait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, XP.LOAD_BUTTON))
        ).click()
        notify(UpgradeStatus.FLASHING, "Uploading — initial 10-minute wait")

        # ── Step 8a: Initial 10-minute wait (keep-alive every 30 s) ───────
        _sleep_with_keepalive(driver, 600)

        # ── Step 8b: Poll OK button every 2 min, up to 10 times ────────────
        ok_found = False
        for poll in range(1, 11):
            notify(UpgradeStatus.FLASHING, f"Checking OK button ({poll}/10)")
            try:
                _wait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, XP.OK_BUTTON))
                )
                ok_found = True
                break
            except TimeoutException:
                if poll < 10:
                    _sleep_with_keepalive(driver, 120)

        if not ok_found:
            notify(UpgradeStatus.FAILED, "OK button not found after 10 attempts (~30 min)")
            return result

        # ── Step 9: Click OK ───────────────────────────────────────────────
        notify(UpgradeStatus.FLASHING, "Clicking OK")
        driver.find_element(By.XPATH, XP.OK_BUTTON).click()

        # ── Step 10: Wait 120 s ────────────────────────────────────────────
        notify(UpgradeStatus.REBOOTING, "Waiting 120 s for reboot to start")
        _sleep_with_keepalive(driver, 120)

        # ── Step 11: Ping every 30 s, up to 6 times ────────────────────────
        device_up = False
        for ping_n in range(1, 7):
            notify(UpgradeStatus.REBOOTING, f"Ping {host} ({ping_n}/6)")
            if _ping(host):
                device_up = True
                notify(UpgradeStatus.REBOOTING, f"{host} is reachable")
                break
            if ping_n < 6:
                time.sleep(30)

        if not device_up:
            notify(UpgradeStatus.FAILED, f"{host} did not respond to ping")
            return result

        # ── Step 12: Re-login with 6 retries, 30 s gap ────────────────────
        login_ok = False
        for login_n in range(1, 7):
            notify(UpgradeStatus.VERIFYING, f"Re-login attempt {login_n}/6")
            try:
                _login(driver, host, user, password)

                login_ok = True
                break
            except Exception as e:
                notify(UpgradeStatus.VERIFYING, f"Re-login {login_n} failed: {e}")
                if login_n < 6:
                    time.sleep(30)

        if not login_ok:
            notify(UpgradeStatus.FAILED, f"Could not re-login to {host}")
            return result

        # ── Step 13: Read new firmware version via SSH ────────────────
        result.fw_version_after = _get_fw_version_ssh(host, user, password)
        notify(
            UpgradeStatus.SUCCESS,
            f"Done. FW: {result.fw_version_before} → {result.fw_version_after}",
        )

    except WebDriverException as e:
        notify(UpgradeStatus.FAILED, f"WebDriver error: {e}")
    except Exception as e:
        notify(UpgradeStatus.FAILED, f"Unexpected error: {e}")
    finally:
        if driver:
            driver.quit()

    return result


# ── Multi-device parallel upgrade ─────────────────────────────────────────────

def upgrade_multiple_devices(
    devices:       List[Dict],
    firmware_path: str,
    headless:      bool = True,
    on_status:     Optional[Callable[[DeviceResult], None]] = None,
) -> Dict[str, DeviceResult]:
    """Run upgrade_device() in parallel — one Chrome instance per device."""
    results: Dict[str, DeviceResult] = {}
    threads: List[threading.Thread]  = []
    lock = threading.Lock()

    def _run(dev: Dict):
        res = upgrade_device(
            host          = dev["host"],
            user          = dev["user"],
            password      = dev["password"],
            firmware_path = firmware_path,
            headless      = headless,
            on_status     = on_status,
        )
        with lock:
            results[dev["host"]] = res

    for dev in devices:
        t = threading.Thread(target=_run, args=(dev,), name=f"upgrade-{dev['host']}")
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(
        description="Upgrade NAX device firmware via Web UI (Selenium)"
    )
    parser.add_argument("--devices",  nargs="+", required=True, help="Device IP(s)")
    parser.add_argument("--user",     required=True,            help="Web UI username")
    parser.add_argument("--password", required=True,            help="Web UI password")
    parser.add_argument("--firmware", required=True,            help="Path to .puf file")
    parser.add_argument("--headless", action="store_true",      help="Run headless")
    args = parser.parse_args()

    device_list = [
        {"host": h, "user": args.user, "password": args.password}
        for h in args.devices
    ]

    def print_status(res: DeviceResult):
        print(f"[{res.host}] {res.status.value}: {res.message}")

    print(f"Starting firmware upgrade for {len(device_list)} device(s)...")
    results = upgrade_multiple_devices(
        devices       = device_list,
        firmware_path = args.firmware,
        headless      = args.headless,
        on_status     = print_status,
    )

    print("\n── Summary ──────────────────────────────────────────────────────")
    for host, res in results.items():
        icon = "OK" if res.status == UpgradeStatus.SUCCESS else "FAIL"
        print(f"  [{icon}] {host}: {res.message}")
        if res.status == UpgradeStatus.FAILED:
            for entry in res.log:
                print(f"        {entry}")


if __name__ == "__main__":
    _cli()


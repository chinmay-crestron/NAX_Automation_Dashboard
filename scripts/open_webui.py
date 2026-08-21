"""
open_webui.py
-------------
Opens the Crestron Device WebUI for a list of IPs, bypasses the SSL warning,
and logs in automatically using the provided credentials.

Requirements:
    pip install selenium openpyxl
    ChromeDriver must be installed and on PATH  -OR-  use:
    pip install webdriver-manager

Usage:
    python open_webui.py                                  # Paste IPs, prompt for credentials
    python open_webui.py --excel devices.xlsx             # Read IPs from Excel
    python open_webui.py --excel devices.xlsx --column "IP Address"
    python open_webui.py --username admin --password pass # Skip credential prompt
    python open_webui.py --delay 2                        # Seconds between each device

Excel file:
    - Any .xlsx file with a column containing IPs.
    - Default column name: "IP" (case-insensitive).
    - Use --column to specify a different column name.

Behaviour:
    - Launches Chrome with SSL errors suppressed (no "Not Secure" warning page).
    - Navigates directly to https://<ip>/userlogin.html for each device.
    - If the SSL warning page is encountered anyway, clicks Advanced -> Proceed.
    - Fills Username and Password fields, then clicks Sign In.
    - All devices are opened in separate tabs in one Chrome window.
    - The browser stays open after all logins complete.
"""

import argparse
import getpass
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

LOGIN_PATH = "/userlogin.html"
_CHROMEDRIVER_PATH = None   # cached after first download


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def read_from_excel(filepath: str, column: str) -> list[str]:
    try:
        import openpyxl
    except ImportError:
        print("ERROR: 'openpyxl' is not installed.  Run: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

    col_index = None
    for i, h in enumerate(headers):
        if h and h.strip().lower() == column.strip().lower():
            col_index = i
            break

    if col_index is None:
        print(f"ERROR: Column '{column}' not found in '{filepath}'.")
        print(f"       Available columns: {[h for h in headers if h]}")
        wb.close()
        sys.exit(1)

    ips = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        val = row[col_index]
        if val is not None:
            ips.append(str(val).strip())
    wb.close()
    return ips


def read_from_paste() -> list[str]:
    print("Paste your IP addresses below (one per line).")
    print("Press Enter on a blank line or type 'done' when finished.\n")
    ips = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        stripped = line.strip()
        if stripped.lower() == "done" or stripped == "":
            break
        if stripped:
            ips.append(stripped)
    return ips


# ---------------------------------------------------------------------------
# Browser / Selenium helpers
# ---------------------------------------------------------------------------

def _ensure_chromedriver() -> str | None:
    """
    Download ChromeDriver once and cache the path.
    Called from the main thread before spawning workers.
    """
    global _CHROMEDRIVER_PATH
    if _CHROMEDRIVER_PATH:
        return _CHROMEDRIVER_PATH
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        _CHROMEDRIVER_PATH = ChromeDriverManager().install()
        return _CHROMEDRIVER_PATH
    except Exception:
        return None  # Fall back to system ChromeDriver


def create_driver() -> object:
    """Return a Chrome WebDriver with SSL errors suppressed."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("ERROR: 'selenium' is not installed.  Run: pip install selenium")
        sys.exit(1)

    options = Options()
    # Suppress SSL certificate errors (self-signed certs on devices)
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors=yes")

    # Hide Selenium automation flags so the device doesn't return 403 Forbidden
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Keep the browser open after script exits
    options.add_experimental_option("detach", True)

    from selenium.webdriver.chrome.service import Service
    if _CHROMEDRIVER_PATH:
        service = Service(_CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    # Patch navigator.webdriver so pages cannot detect Selenium via JS
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver


def bypass_ssl_warning(driver) -> bool:
    """
    If Chrome's 'Your connection is not private' page is showing,
    click Advanced → Proceed.  Returns True if bypass was needed.
    """
    from selenium.webdriver.common.by import By
    try:
        adv_btn = driver.find_element(By.ID, "details-button")
        adv_btn.click()
        time.sleep(0.5)
        proceed_link = driver.find_element(By.ID, "proceed-link")
        proceed_link.click()
        return True
    except Exception:
        return False


def fill_field(driver, element, value: str) -> None:
    """
    Fill a form input using only real keyboard events.
    No JavaScript injection — works reliably with Angular/React forms.
    """
    from selenium.webdriver.common.keys import Keys

    element.click()
    time.sleep(0.2)
    # Select all existing text and delete it
    element.send_keys(Keys.CONTROL + "a")
    element.send_keys(Keys.DELETE)
    time.sleep(0.1)
    # Type character by character to mimic human input
    for char in value:
        element.send_keys(char)
        time.sleep(0.04)


def find_sign_in_button(driver):
    """Try multiple strategies to locate the Sign In button."""
    from selenium.webdriver.common.by import By

    strategies = [
        (By.XPATH,       "//button[contains(normalize-space(), 'Sign In')]"),
        (By.XPATH,       "//button[contains(normalize-space(), 'Sign in')]"),
        (By.XPATH,       "//button[contains(normalize-space(), 'Login')]"),
        (By.XPATH,       "//input[@type='submit']"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.XPATH,        "//button"),          # last resort: first button on page
    ]
    for by, selector in strategies:
        try:
            btn = driver.find_element(by, selector)
            if btn.is_displayed():
                return btn
        except Exception:
            continue
    return None


def do_login(driver, ip: str, username: str, password: str, new_tab: bool) -> None:
    """Navigate to a device login page and sign in."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    url = f"https://{ip}{LOGIN_PATH}"
    print(f"  [{ip}]  Opening {url}")

    if new_tab:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])

    driver.get(url)
    time.sleep(1.5)

    # Bypass SSL warning if it appears despite Chrome flags
    if "ERR_CERT" in driver.page_source or "not private" in driver.page_source.lower():
        print(f"  [{ip}]  SSL warning detected — bypassing...")
        bypass_ssl_warning(driver)
        time.sleep(1.5)

    wait = WebDriverWait(driver, 15)

    try:
        # Wait until the username field is interactable
        user_field = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Username']"))
        )
        pass_field = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Password']"))
        )

        fill_field(driver, user_field, username)
        time.sleep(0.3)
        fill_field(driver, pass_field, password)
        time.sleep(0.3)

        sign_in_btn = find_sign_in_button(driver)
        if sign_in_btn is None:
            raise RuntimeError("Sign In button not found on the page.")
        sign_in_btn.click()

        print(f"  [{ip}]  Login submitted successfully.")

    except Exception as exc:
        print(f"  [{ip}]  WARNING: Login failed — {exc}")


def login_device_parallel(ip: str, username: str, password: str) -> str:
    """
    Open a dedicated Chrome window for one device and log in.
    Designed to run inside a ThreadPoolExecutor worker.
    Returns a status string.
    """
    try:
        driver = create_driver()
        do_login(driver, ip, username, password, new_tab=False)
        return f"  [{ip}]  OK"
    except Exception as exc:
        return f"  [{ip}]  FAILED — {exc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Open Crestron device WebUI pages and log in automatically."
    )
    parser.add_argument("--excel", "-e", metavar="FILE",
                        help="Path to an Excel (.xlsx) file containing IP addresses.")
    parser.add_argument("--column", "-c", default="IP", metavar="COLUMN",
                        help="Column name in the Excel sheet (default: 'IP').")
    parser.add_argument("--username", "-u", default=None,
                        help="WebUI username (prompted if not provided).")
    parser.add_argument("--password", "-p", default=None,
                        help="WebUI password (prompted if not provided).")
    parser.add_argument("--workers", "-w", type=int, default=0, metavar="N",
                        help="Max parallel browser windows (default: all devices at once).")
    args = parser.parse_args()

    # Collect IPs
    if args.excel:
        ips = read_from_excel(args.excel, args.column)
    else:
        ips = read_from_paste()

    valid_ips = [ip for ip in ips if ip]
    if not valid_ips:
        print("No valid IPs found. Exiting.")
        sys.exit(0)

    # Collect credentials
    username = args.username or input("\nEnter WebUI username: ").strip()
    password = args.password or getpass.getpass("Enter WebUI password: ")

    # Download ChromeDriver once before spawning parallel threads
    print("\nPreparing ChromeDriver...")
    _ensure_chromedriver()

    workers = args.workers if args.workers > 0 else len(valid_ips)
    print(f"Opening {len(valid_ips)} device(s) in parallel ({workers} concurrent windows)...\n")

    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(login_device_parallel, ip, username, password): ip
            for ip in valid_ips
        }
        for future in as_completed(futures):
            msg = future.result()
            print(msg)

    print("\nAll done. All browser windows will stay open.")


if __name__ == "__main__":
    main()


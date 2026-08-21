from playwright.sync_api import sync_playwright
import time

HOST = "172.30.2.147"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--ignore-certificate-errors"])
    ctx  = browser.new_context(ignore_https_errors=True)
    page = ctx.new_page()

    print("Navigating to https://" + HOST + "/index_device.html")
    page.goto(f"https://{HOST}/index_device.html", wait_until="domcontentloaded", timeout=30000)
    print("URL :", page.url)
    print("Title:", page.title())
    time.sleep(3)  # wait for Angular/JS to render login form

    # List all inputs
    inputs = page.locator("input").all()
    print(f"\nAll inputs ({len(inputs)}):")
    for i, el in enumerate(inputs[:15]):
        pid  = el.get_attribute("id") or ""
        ptype = el.get_attribute("type") or ""
        vis  = el.is_visible()
        print(f"  [{i}] id={pid!r:40s} type={ptype!r:12s} visible={vis}")

    # Check exact XPaths the user gave
    print("\nXPath checks:")
    xpaths = [
        "//input[@id='cred_userid_inputtext']",
        "//input[@id='cred_password_inputtext']",
        "//button[@id='submitBtn']",
        "//button[@id='submitBtn']/span[@class='ui-button-text ui-c']",
    ]
    for xp in xpaths:
        matches = page.locator(f"xpath={xp}").all()
        vis = matches[0].is_visible() if matches else "N/A"
        print(f"  {len(matches)} match  visible={vis}  -> {xp}")

    # Also dump partial page HTML around login area
    try:
        html = page.inner_html("body")
        # print first 2000 chars for context
        print("\n--- body HTML (first 2000 chars) ---")
        print(html[:2000])
    except Exception as e:
        print("body dump failed:", e)

    time.sleep(3)
    ctx.close()
    browser.close()

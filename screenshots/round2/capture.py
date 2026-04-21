"""
Selenium screenshot script for the Streamlit app at http://localhost:8504
Captures login page, full dashboard, and cropped sidebar.
"""

import time
import os
from io import BytesIO
from PIL import Image

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SAVE_DIR = "D:/hub-cluster-optimizer-v2/screenshots/round2"
BASE_URL = "http://localhost:8504"
USERNAME = "admin"
PASSWORD = "shadowfax2026"
WIDTH = 1600
HEIGHT = 1000

os.makedirs(SAVE_DIR, exist_ok=True)

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument(f"--window-size={WIDTH},{HEIGHT}")
opts.add_argument("--force-device-scale-factor=1")

driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 20)

try:
    # ── 1. LOGIN PAGE ──────────────────────────────────────────────────────────
    driver.get(BASE_URL)
    time.sleep(3)  # let Streamlit fully render

    login_path = os.path.join(SAVE_DIR, "login2.png")
    driver.save_screenshot(login_path)
    print("[1] Saved login page  -> " + login_path)
    print("    Page title: " + driver.title)
    print("    Page source snippet:\n" + driver.page_source[:2000])

    # ── 2. LOG IN ──────────────────────────────────────────────────────────────
    # Look for username / password fields in Streamlit
    page_src = driver.page_source

    # Try Streamlit text_input elements (they render as <input type="text"> / <input type="password">)
    inputs = driver.find_elements(By.CSS_SELECTOR, "input")
    print(f"\n[2] Found {len(inputs)} input elements on the login page:")
    for i, inp in enumerate(inputs):
        print(f"    [{i}] type={inp.get_attribute('type')!r}  "
              f"placeholder={inp.get_attribute('placeholder')!r}  "
              f"aria-label={inp.get_attribute('aria-label')!r}  "
              f"id={inp.get_attribute('id')!r}")

    # Identify username and password fields
    username_input = None
    password_input = None

    for inp in inputs:
        t = (inp.get_attribute("type") or "").lower()
        ph = (inp.get_attribute("placeholder") or "").lower()
        lbl = (inp.get_attribute("aria-label") or "").lower()
        combined = ph + " " + lbl
        if t == "password":
            password_input = inp
        elif "user" in combined or "login" in combined or "email" in combined or "name" in combined:
            username_input = inp
        elif username_input is None and t in ("text", ""):
            username_input = inp  # fallback: first text input

    if username_input:
        username_input.clear()
        username_input.send_keys(USERNAME)
        print(f"    Typed username into: {username_input.get_attribute('aria-label') or username_input.get_attribute('placeholder')}")
    else:
        print("    WARNING: could not find username field")

    if password_input:
        password_input.clear()
        password_input.send_keys(PASSWORD)
        print(f"    Typed password into: {password_input.get_attribute('aria-label') or password_input.get_attribute('placeholder')}")
    else:
        print("    WARNING: could not find password field")

    # Click the login / submit button
    # Try common button texts
    submitted = False
    for btn_text in ("Login", "Log in", "Sign in", "Submit", "Enter"):
        btns = driver.find_elements(By.XPATH, f"//button[contains(., '{btn_text}')]")
        if btns:
            btns[0].click()
            print(f"    Clicked button: '{btn_text}'")
            submitted = True
            break

    if not submitted:
        # Try pressing Enter on the password field
        from selenium.webdriver.common.keys import Keys
        if password_input:
            password_input.send_keys(Keys.RETURN)
            print("    Pressed Enter on password field")
        elif username_input:
            username_input.send_keys(Keys.RETURN)
            print("    Pressed Enter on username field")

    # ── 3. WAIT FOR DASHBOARD ─────────────────────────────────────────────────
    print("\n[3] Waiting for dashboard to load...")
    time.sleep(5)

    # Wait until the Streamlit spinner is gone (or a known dashboard element appears)
    try:
        wait.until(lambda d: "stSpinner" not in d.page_source or True)
    except Exception:
        pass

    # Extra wait if still on login-looking page
    for attempt in range(6):
        src = driver.page_source.lower()
        if "password" not in src or attempt >= 5:
            break
        print(f"    Still on login page (attempt {attempt+1}), waiting 3s …")
        time.sleep(3)

    print(f"    Current URL: {driver.current_url}")
    print(f"    Page title : {driver.title}")

    # ── 4. FULL DASHBOARD SCREENSHOT ──────────────────────────────────────────
    # Scroll to top before screenshot
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    dash_path = os.path.join(SAVE_DIR, "dashboard2.png")
    driver.save_screenshot(dash_path)
    print("\n[4] Saved dashboard -> " + dash_path)

    # 5. SIDEBAR CROP
    img = Image.open(dash_path)
    sidebar_width = 280
    sidebar = img.crop((0, 0, sidebar_width, img.height))
    sidebar_path = os.path.join(SAVE_DIR, "sidebar2.png")
    sidebar.save(sidebar_path)
    print("[5] Saved sidebar crop -> " + sidebar_path)
    print("    Sidebar size: " + str(sidebar.size))

    # ── 6. DESCRIBE WHAT WE SEE ───────────────────────────────────────────────
    print("\n[6] Page source summary (first 3000 chars of body text):")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(body_text[:3000])

finally:
    driver.quit()
    print("\nDone. Browser closed.")

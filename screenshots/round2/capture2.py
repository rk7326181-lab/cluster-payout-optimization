# -*- coding: utf-8 -*-
"""
Improved Selenium screenshot script.
Waits for Streamlit React app to fully render before each screenshot.
"""

import time
import os
import sys
from PIL import Image

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

SAVE_DIR = "D:/hub-cluster-optimizer-v2/screenshots/round2"
BASE_URL = "http://localhost:8504"
USERNAME = "admin"
PASSWORD = "shadowfax2026"
WIDTH = 1600
HEIGHT = 900

os.makedirs(SAVE_DIR, exist_ok=True)

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=" + str(WIDTH) + "," + str(HEIGHT))
opts.add_argument("--force-device-scale-factor=1")
opts.add_argument("--disable-gpu")

driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 30)

def wait_for_streamlit(driver, timeout=30):
    """Wait until Streamlit spinner is gone and content is loaded."""
    time.sleep(2)
    try:
        # Wait for the stApp element to exist
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='stApp']"))
        )
    except Exception as e:
        print("  (stApp wait timed out: " + str(e) + ")")
    # Extra settle time
    time.sleep(2)

def save_screenshot(driver, path):
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)
    driver.save_screenshot(path)
    img = Image.open(path)
    print("  Saved " + path + " (" + str(img.size[0]) + "x" + str(img.size[1]) + ")")
    return img

try:
    # ── STEP 1: Login page ───────────────────────────────────────────────────
    print("=== Step 1: Loading login page ===")
    driver.get(BASE_URL)
    wait_for_streamlit(driver)

    # Print visible text
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print("Visible text on page (first 500 chars):")
    print(body_text[:500])
    print("---")

    login_path = os.path.join(SAVE_DIR, "login2.png")
    save_screenshot(driver, login_path)

    # ── STEP 2: Fill in credentials ──────────────────────────────────────────
    print("\n=== Step 2: Logging in ===")
    inputs = driver.find_elements(By.CSS_SELECTOR, "input")
    print("Input fields found: " + str(len(inputs)))
    for i, inp in enumerate(inputs):
        print("  [" + str(i) + "] type=" + str(inp.get_attribute("type")) +
              "  aria-label=" + str(inp.get_attribute("aria-label")) +
              "  placeholder=" + str(inp.get_attribute("placeholder")))

    # Find email/username and password fields
    email_field = None
    pass_field = None
    for inp in inputs:
        t = (inp.get_attribute("type") or "").lower()
        lbl = (inp.get_attribute("aria-label") or "").lower()
        ph = (inp.get_attribute("placeholder") or "").lower()
        combined = lbl + " " + ph
        if t == "password":
            pass_field = inp
        elif "email" in combined or "user" in combined or "name" in combined:
            email_field = inp
        elif email_field is None and t in ("text", "email", ""):
            email_field = inp

    if email_field:
        email_field.clear()
        email_field.send_keys(USERNAME)
        print("  Entered username in: " + str(email_field.get_attribute("aria-label")))
    else:
        print("  WARNING: no email field found")

    if pass_field:
        pass_field.clear()
        pass_field.send_keys(PASSWORD)
        print("  Entered password in: " + str(pass_field.get_attribute("aria-label")))
    else:
        print("  WARNING: no password field found")

    # Click login button
    clicked = False
    for btn_text in ("Login", "Log in", "Sign in", "Submit", "Continue"):
        btns = driver.find_elements(By.XPATH, "//button[contains(., '" + btn_text + "')]")
        if btns:
            btns[0].click()
            print("  Clicked: " + btn_text)
            clicked = True
            break

    if not clicked:
        # Press Enter
        if pass_field:
            pass_field.send_keys(Keys.RETURN)
            print("  Pressed Enter on password field")
        elif email_field:
            email_field.send_keys(Keys.RETURN)
            print("  Pressed Enter on email field")

    # ── STEP 3: Wait for dashboard ───────────────────────────────────────────
    print("\n=== Step 3: Waiting for dashboard ===")
    wait_for_streamlit(driver)

    # Check if login succeeded
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print("Visible text after login (first 800 chars):")
    print(body_text[:800])
    print("---")
    print("Current URL: " + driver.current_url)

    # If still on login, try again
    if "email" in body_text.lower() and "password" in body_text.lower() and "Shadowfax" not in body_text:
        print("  Still on login page, trying again...")
        inputs = driver.find_elements(By.CSS_SELECTOR, "input")
        for inp in inputs:
            t = (inp.get_attribute("type") or "").lower()
            lbl = (inp.get_attribute("aria-label") or "").lower()
            if "email" in lbl or t in ("text", "email"):
                inp.clear()
                inp.send_keys(USERNAME)
            elif t == "password":
                inp.clear()
                inp.send_keys(PASSWORD)
                inp.send_keys(Keys.RETURN)
        time.sleep(5)
        wait_for_streamlit(driver)
        body_text = driver.find_element(By.TAG_NAME, "body").text
        print("Visible text after 2nd attempt (first 400 chars):")
        print(body_text[:400])

    # ── STEP 4: Full dashboard screenshot ───────────────────────────────────
    print("\n=== Step 4: Dashboard screenshot ===")
    # Set taller window for more content
    driver.set_window_size(WIDTH, 1100)
    time.sleep(1)
    dash_path = os.path.join(SAVE_DIR, "dashboard2.png")
    save_screenshot(driver, dash_path)

    # ── STEP 5: Sidebar crop ─────────────────────────────────────────────────
    print("\n=== Step 5: Sidebar crop ===")
    img = Image.open(dash_path)
    sidebar_width = 280
    sidebar = img.crop((0, 0, sidebar_width, img.height))
    sidebar_path = os.path.join(SAVE_DIR, "sidebar2.png")
    sidebar.save(sidebar_path)
    print("  Saved sidebar " + sidebar_path + " (" + str(sidebar.size[0]) + "x" + str(sidebar.size[1]) + ")")

    # ── STEP 6: Final body text summary ─────────────────────────────────────
    print("\n=== Step 6: Full page text (up to 3000 chars) ===")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(body_text[:3000])

finally:
    driver.quit()
    print("\nDone.")

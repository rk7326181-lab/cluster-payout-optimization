# -*- coding: utf-8 -*-
"""
Final screenshot capture - handles tall login page and proper scrolling.
"""

import time
import os
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
HEIGHT = 2200  # Extra tall to capture full login page

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

def wait_for_app(driver, extra_secs=4):
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='stApp']"))
        )
    except Exception as e:
        print("  (wait warning: " + str(e) + ")")
    time.sleep(extra_secs)

def full_page_screenshot(driver, path):
    """Take a full-page screenshot using CDP."""
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)
    driver.save_screenshot(path)
    img = Image.open(path)
    print("Saved: " + path + "  size=" + str(img.size))
    return img

try:
    # ─── LOGIN PAGE ───────────────────────────────────────────────────────────
    print("Loading login page (tall window)...")
    driver.get(BASE_URL)
    wait_for_app(driver, extra_secs=5)

    # Get page dimensions
    page_h = driver.execute_script("return document.body.scrollHeight")
    page_w = driver.execute_script("return document.body.scrollWidth")
    print("Login page scroll size: " + str(page_w) + "x" + str(page_h))

    # Resize window to fit full page
    actual_h = min(page_h + 100, 3000)
    driver.set_window_size(WIDTH, actual_h)
    time.sleep(1)

    login_path = os.path.join(SAVE_DIR, "login2.png")
    img_login = full_page_screenshot(driver, login_path)

    # ─── LOGIN ────────────────────────────────────────────────────────────────
    print("Logging in...")
    inputs = driver.find_elements(By.CSS_SELECTOR, "input")
    email_inp = None
    pass_inp = None
    for inp in inputs:
        t = (inp.get_attribute("type") or "").lower()
        lbl = (inp.get_attribute("aria-label") or "").lower()
        if t == "password":
            pass_inp = inp
        elif email_inp is None and ("email" in lbl or "user" in lbl or t in ("text", "email")):
            email_inp = inp

    if email_inp:
        email_inp.clear()
        email_inp.send_keys(USERNAME)
        print("  Username entered")
    if pass_inp:
        pass_inp.clear()
        pass_inp.send_keys(PASSWORD)
        pass_inp.send_keys(Keys.RETURN)
        print("  Password entered, form submitted")

    # ─── WAIT FOR DASHBOARD ───────────────────────────────────────────────────
    print("Waiting for dashboard...")
    wait_for_app(driver, extra_secs=5)

    # Confirm dashboard
    try:
        WebDriverWait(driver, 15).until(
            EC.text_to_be_present_in_element(
                (By.CSS_SELECTOR, "[data-testid='stSidebar']"), "MAIN MENU"
            )
        )
        print("Dashboard confirmed (MAIN MENU visible in sidebar)")
    except Exception:
        print("Warning: MAIN MENU not detected in sidebar timeout")

    time.sleep(2)

    # ─── DASHBOARD ────────────────────────────────────────────────────────────
    print("Taking dashboard screenshot...")
    driver.set_window_size(1600, 1100)
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    dash_path = os.path.join(SAVE_DIR, "dashboard2.png")
    img_dash = full_page_screenshot(driver, dash_path)

    # ─── SIDEBAR CROP ─────────────────────────────────────────────────────────
    print("Cropping sidebar (left 280px)...")
    sidebar = img_dash.crop((0, 0, 280, img_dash.height))
    sidebar_path = os.path.join(SAVE_DIR, "sidebar2.png")
    sidebar.save(sidebar_path)
    print("Sidebar saved: " + sidebar_path + "  size=" + str(sidebar.size))

    # ─── PAGE TEXT SUMMARY ────────────────────────────────────────────────────
    print("\n=== DASHBOARD PAGE TEXT ===")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(body_text[:2500])

    print("\n=== KEY DOM ELEMENTS ===")
    sidebar_el = driver.find_elements(By.CSS_SELECTOR, "[data-testid='stSidebar']")
    main_el = driver.find_elements(By.CSS_SELECTOR, "[data-testid='stMain']")
    print("Sidebar text: " + (sidebar_el[0].text[:300] if sidebar_el else "NOT FOUND"))
    print("Main text: " + (main_el[0].text[:300] if main_el else "NOT FOUND"))

finally:
    driver.quit()
    print("\nDone.")

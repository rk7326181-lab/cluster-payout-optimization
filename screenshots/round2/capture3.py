# -*- coding: utf-8 -*-
"""
Final screenshot capture for Streamlit app.
Uses stApp data-testid to confirm full render, then screenshots.
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
HEIGHT = 960

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

def wait_for_app(driver, timeout=30):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='stApp']"))
        )
    except Exception as e:
        print("  (wait warning: " + str(e) + ")")
    time.sleep(3)

def save_shot(driver, path):
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)
    driver.save_screenshot(path)
    img = Image.open(path)
    print("Saved: " + path + "  size=" + str(img.size))
    return img

try:
    # ─── LOGIN PAGE ───────────────────────────────────────────────────────────
    print("Loading login page...")
    driver.get(BASE_URL)
    wait_for_app(driver)
    # Extra wait for full Streamlit render
    time.sleep(4)

    login_path = os.path.join(SAVE_DIR, "login2.png")
    img_login = save_shot(driver, login_path)
    print("Login page size: " + str(img_login.size))

    # ─── LOGIN ────────────────────────────────────────────────────────────────
    print("Filling credentials...")
    inputs = driver.find_elements(By.CSS_SELECTOR, "input")
    email_inp = None
    pass_inp = None
    for inp in inputs:
        t = (inp.get_attribute("type") or "").lower()
        lbl = (inp.get_attribute("aria-label") or "").lower()
        if t == "password":
            pass_inp = inp
        elif "email" in lbl or "user" in lbl or t in ("text", "email"):
            if email_inp is None:
                email_inp = inp

    if email_inp:
        email_inp.clear()
        email_inp.send_keys(USERNAME)
    if pass_inp:
        pass_inp.clear()
        pass_inp.send_keys(PASSWORD)
        pass_inp.send_keys(Keys.RETURN)

    print("Credentials submitted. Waiting for dashboard...")

    # ─── WAIT FOR DASHBOARD ───────────────────────────────────────────────────
    wait_for_app(driver)
    # Also wait until sidebar menu items are visible
    try:
        WebDriverWait(driver, 15).until(
            EC.text_to_be_present_in_element(
                (By.CSS_SELECTOR, "[data-testid='stApp']"),
                "MAIN MENU"
            )
        )
        print("Dashboard loaded (MAIN MENU visible)")
    except Exception:
        print("Timeout waiting for MAIN MENU - proceeding anyway")
    time.sleep(3)

    # ─── DASHBOARD SCREENSHOT ─────────────────────────────────────────────────
    print("Taking dashboard screenshot...")
    driver.set_window_size(WIDTH, 1100)
    time.sleep(1)
    dash_path = os.path.join(SAVE_DIR, "dashboard2.png")
    img_dash = save_shot(driver, dash_path)

    # ─── SIDEBAR CROP ─────────────────────────────────────────────────────────
    print("Cropping sidebar...")
    sidebar = img_dash.crop((0, 0, 280, img_dash.height))
    sidebar_path = os.path.join(SAVE_DIR, "sidebar2.png")
    sidebar.save(sidebar_path)
    print("Sidebar saved: " + sidebar_path + "  size=" + str(sidebar.size))

    # ─── SUMMARISE VISIBLE CONTENT ────────────────────────────────────────────
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print("\n=== PAGE TEXT AFTER LOGIN (first 3000 chars) ===")
    print(body_text[:3000])

    # Check specific dashboard elements
    print("\n=== CHECKING KEY ELEMENTS ===")
    for selector, desc in [
        ("[data-testid='stSidebar']", "Sidebar"),
        ("[data-testid='stMain']", "Main content area"),
        ("[data-testid='stHeader']", "Header"),
    ]:
        elems = driver.find_elements(By.CSS_SELECTOR, selector)
        if elems:
            print(desc + " found: " + elems[0].text[:200])
        else:
            print(desc + " NOT found")

finally:
    driver.quit()
    print("\nAll done.")

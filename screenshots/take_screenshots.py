"""
Screenshot script for Streamlit app at http://localhost:8503
Uses Selenium with Chrome to capture login page, dashboard, and sidebar.
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

SCREENSHOTS_DIR = r"d:\hub-cluster-optimizer-v2\screenshots"
APP_URL = "http://localhost:8503"

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1400, 900)
    return driver

def wait_for_streamlit(driver, timeout=20):
    """Wait for Streamlit to finish loading."""
    time.sleep(3)
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass
    time.sleep(2)

def screenshot_login(driver):
    print("Navigating to app...")
    driver.get(APP_URL)
    wait_for_streamlit(driver)

    # Save login page screenshot
    path = os.path.join(SCREENSHOTS_DIR, "login.png")
    driver.save_screenshot(path)
    print(f"Saved login page: {path}")
    return path

def find_and_fill_login(driver):
    """Find login form fields and fill them in."""
    wait = WebDriverWait(driver, 15)

    # Streamlit text inputs
    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
    password_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")

    print(f"Found {len(inputs)} text inputs and {len(password_inputs)} password inputs")

    username_filled = False
    password_filled = False

    # Fill username
    if inputs:
        inputs[0].clear()
        inputs[0].send_keys("admin")
        username_filled = True
        print("Filled username field")

    # Fill password
    if password_inputs:
        password_inputs[0].clear()
        password_inputs[0].send_keys("shadowfax2026")
        password_filled = True
        print("Filled password field")

    if not username_filled or not password_filled:
        # Try Streamlit-specific approach - look for all inputs
        all_inputs = driver.find_elements(By.CSS_SELECTOR, "input")
        print(f"All inputs found: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs):
            itype = inp.get_attribute("type")
            iplaceholder = inp.get_attribute("placeholder") or ""
            iaria = inp.get_attribute("aria-label") or ""
            print(f"  Input {i}: type={itype}, placeholder={iplaceholder}, aria-label={iaria}")

        for inp in all_inputs:
            itype = inp.get_attribute("type") or "text"
            iplaceholder = (inp.get_attribute("placeholder") or "").lower()
            iaria = (inp.get_attribute("aria-label") or "").lower()

            if not username_filled and ("user" in iplaceholder or "user" in iaria or "login" in iplaceholder or itype == "text"):
                inp.clear()
                inp.send_keys("admin")
                username_filled = True
                print(f"Filled username via fallback: {iplaceholder or iaria}")
            elif not password_filled and itype == "password":
                inp.clear()
                inp.send_keys("shadowfax2026")
                password_filled = True
                print(f"Filled password via fallback")

    return username_filled, password_filled

def click_login_button(driver):
    """Find and click the login/submit button."""
    # Try various button selectors
    selectors = [
        "button[kind='primaryFormSubmit']",
        "button[kind='primary']",
        "button.stButton > button",
        "button[data-testid='baseButton-primary']",
        "div.stButton > button",
        "button",
    ]

    for sel in selectors:
        buttons = driver.find_elements(By.CSS_SELECTOR, sel)
        for btn in buttons:
            text = btn.text.lower()
            if any(word in text for word in ["login", "sign in", "log in", "submit", "enter"]):
                safe_text = btn.text.encode('ascii', 'replace').decode('ascii')
                print(f"Clicking button: '{safe_text}' (selector: {sel})")
                btn.click()
                return True

    # Last resort: click first visible button
    buttons = driver.find_elements(By.CSS_SELECTOR, "button")
    visible_buttons = [b for b in buttons if b.is_displayed()]
    safe_names = [b.text.encode('ascii','replace').decode('ascii') for b in visible_buttons]
    print(f"Visible buttons: {safe_names}")
    if visible_buttons:
        print(f"Clicking first visible button: '{safe_names[0]}'")
        visible_buttons[0].click()
        return True

    return False

def screenshot_dashboard(driver):
    """Log in and screenshot the main dashboard."""
    u_filled, p_filled = find_and_fill_login(driver)

    if not u_filled and not p_filled:
        print("WARNING: Could not find login form fields!")
        # Save what we see anyway
        path = os.path.join(SCREENSHOTS_DIR, "dashboard.png")
        driver.save_screenshot(path)
        return path

    # Click login
    clicked = click_login_button(driver)
    if not clicked:
        print("WARNING: Could not find login button, pressing Enter instead")
        from selenium.webdriver.common.keys import Keys
        inputs = driver.find_elements(By.CSS_SELECTOR, "input")
        if inputs:
            inputs[-1].send_keys(Keys.RETURN)

    # Wait for dashboard to load
    print("Waiting for dashboard to load...")
    time.sleep(5)
    wait_for_streamlit(driver)

    path = os.path.join(SCREENSHOTS_DIR, "dashboard.png")
    driver.save_screenshot(path)
    print(f"Saved dashboard: {path}")
    return path

def screenshot_sidebar(driver):
    """Screenshot the sidebar clearly - scroll to top and zoom in on sidebar."""
    # First scroll to top
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    # Try to expand the sidebar if it's collapsed
    try:
        # Check for sidebar toggle button
        toggle_buttons = driver.find_elements(By.CSS_SELECTOR,
            "[data-testid='collapsedControl'], button[aria-label*='sidebar'], button[title*='sidebar']")
        for tb in toggle_buttons:
            if tb.is_displayed():
                print("Found sidebar toggle, clicking it")
                tb.click()
                time.sleep(2)
                break
    except Exception as e:
        print(f"Sidebar toggle attempt: {e}")

    # Take full screenshot
    path = os.path.join(SCREENSHOTS_DIR, "sidebar.png")
    driver.save_screenshot(path)
    print(f"Saved sidebar: {path}")

    # Also try to crop/highlight the sidebar region using PIL
    try:
        from PIL import Image
        img = Image.open(path)
        width, height = img.size
        print(f"Full screenshot size: {width}x{height}")

        # Streamlit sidebar is typically on the left, ~250-300px wide
        sidebar_width = min(320, width // 4)
        sidebar = img.crop((0, 0, sidebar_width, height))
        sidebar_path = os.path.join(SCREENSHOTS_DIR, "sidebar_cropped.png")
        sidebar.save(sidebar_path)
        print(f"Saved cropped sidebar: {sidebar_path}")
    except Exception as e:
        print(f"PIL crop failed: {e}")

    return path

def main():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    print("Setting up Chrome WebDriver...")
    driver = None
    try:
        driver = setup_driver()
        print("Chrome WebDriver ready!")

        # 1. Screenshot login page
        print("\n--- Step 1: Login Page ---")
        screenshot_login(driver)

        # 2. Log in and screenshot dashboard
        print("\n--- Step 2: Dashboard ---")
        screenshot_dashboard(driver)

        # 3. Screenshot sidebar
        print("\n--- Step 3: Sidebar ---")
        screenshot_sidebar(driver)

        # 4. Save page source for analysis
        html_path = os.path.join(SCREENSHOTS_DIR, "dashboard_source.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"\nSaved page source: {html_path}")

        print("\nAll screenshots complete!")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

        # Fallback: save page source via requests
        print("\nFalling back to requests-based HTML capture...")
        import requests
        try:
            r = requests.get(APP_URL, timeout=10)
            html_path = os.path.join(SCREENSHOTS_DIR, "screenshot_html.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"Saved HTML: {html_path}")
        except Exception as e2:
            print(f"Requests fallback also failed: {e2}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()

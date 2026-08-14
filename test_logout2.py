"""Test logging out by clicking the Sign out button."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Go to the SSO portal
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=15000)
    time.sleep(5)
    
    # Find and click the Sign out link
    body_before = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"Before logout: {body_before[:100]}")
    
    # Look for sign out link/button
    try:
        # Try clicking the sign out link
        signout = page.locator('a:has-text("Sign out"), button:has-text("Sign out")').first
        signout.click(timeout=5000)
        print("[+] Sign out clicked")
        time.sleep(5)
    except Exception as e:
        print(f"[!] Sign out error: {e}")
    
    body_after = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"After logout: {body_after[:200]}")
    
    page.close()
    context.close()

"""Test logging out of the current AWS session."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Navigate to sign out
    page.goto('https://view.awsapps.com/start/#/signout', wait_until='domcontentloaded', timeout=15000)
    time.sleep(5)
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"After signout navigation: {body[:200]}")
    
    # Try the actual sign out endpoint
    page.goto('https://view.awsapps.com/start/api/session/signout', wait_until='domcontentloaded', timeout=15000)
    time.sleep(5)
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"After API signout: {body[:200]}")
    
    page.close()
    context.close()

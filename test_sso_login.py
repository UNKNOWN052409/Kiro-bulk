"""Test login page via SSO portal directly."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    print("Navigating to SSO portal...")
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(15)
    
    print(f"URL: {page.url[:80]}")
    
    try:
        html = page.content()
        print(f"HTML length: {len(html)}")
    except Exception as e:
        print(f"content() error: {e}")
    
    try:
        inputs = page.locator('input').count()
        print(f"Inputs: {inputs}")
    except Exception as e:
        print(f"input error: {e}")
    
    try:
        btns = page.locator('button').count()
        print(f"Buttons: {btns}")
    except Exception as e:
        print(f"button error: {e}")
    
    # Try to get body text via JS (might work on SSO portal)
    try:
        body = page.evaluate("document.body ? document.body.innerText : 'no body'")
        print(f"Body text: {body[:100] if body else 'empty'}")
    except Exception as e:
        print(f"JS error: {e}")
    
    page.close()
    context.close()

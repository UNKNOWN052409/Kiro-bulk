from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Check what page we're on
    print(f"Current URL: {page.url[:100]}")
    
    # Try to get body
    try:
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f"Body: {body[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    
    page.close()
    context.close()

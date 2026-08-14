from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    
    # Clear all cookies
    context.clear_cookies()
    print("Cookies cleared via Playwright!")
    
    # Also navigate to about:blank
    try:
        page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
        time.sleep(2)
        print(f"URL: {page.url}")
    except:
        pass
    
    context.close()

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0]
    
    for _ in range(10):
        time.sleep(2)
        try:
            body = page.evaluate("document.body.innerText")
            print(f"[{_ * 2}s] URL: {page.url[:100]}")
            print(f"  Body: {body[:100]}")
        except Exception as e:
            print(f"  Error: {e}")
    
    context.close()

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    
    for _ in range(15):
        time.sleep(3)
        try:
            body = page.evaluate("document.body ? document.body.innerText : ''")
            print(f"[{_ * 3}s] URL: {page.url[:80]}")
            print(f"  Body: {body[:150]}")
            if 'Get started' in body or 'Email' in body:
                print("\n*** Logged out - on login page! ***")
                break
        except:
            pass
    
    context.close()

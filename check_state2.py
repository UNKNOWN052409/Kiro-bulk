from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else None
    
    if page:
        print(f"URL: {page.url}")
        try:
            body = page.evaluate("document.body ? document.body.innerText : 'NO BODY'")
            print(f"Body: {body[:200]}")
        except:
            print("Body: (cannot access)")
    else:
        print("No pages!")
    
    context.close()

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    # Close all pages
    for pg in context.pages:
        try: pg.close()
        except: pass
    
    page = context.new_page()
    page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
    time.sleep(2)
    print("State cleared. Browser ready.")
    
    context.close()

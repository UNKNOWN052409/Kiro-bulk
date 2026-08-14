"""Wait much longer for the SPA to render."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    
    for i in range(30):
        time.sleep(5)
        try:
            ready = page.evaluate("document.readyState")
            body_len = page.evaluate("document.body ? document.body.innerText.length : 0")
            container = page.evaluate("document.getElementById('main-container') ? document.getElementById('main-container').innerHTML.length : 0")
            print(f"[{i*5}s] readyState: {ready} | bodyText: {body_len} | mainContainer: {container}")
            if body_len > 50:
                break
        except Exception as e:
            print(f"[{i*5}s] Error: {e}")
    
    # Get the body text
    try:
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f"\nFinal body: {body[:200] if body else 'empty'}")
    except:
        pass
    
    page.close()
    context.close()

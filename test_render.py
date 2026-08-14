from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(20)
    
    try:
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f"Body: {body[:100] if body else 'empty'}")
        print(f"Body length: {len(body) if body else 0}")
    except Exception as e:
        print(f"JS error: {e}")
    
    try:
        inputs = page.locator('input').count()
        print(f"Inputs: {inputs}")
    except:
        print("Inputs: error")
    
    page.close()
    context.close()

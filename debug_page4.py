"""Debug: wait longer for the SPA to render."""
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto('https://view.awsapps.com/start/#/device?user_code=TEST-TEST',
                      wait_until='commit', timeout=30000)
        except Exception:
            pass
        
        # Wait much longer for the SPA to render
        for i in range(30):
            time.sleep(1.0)
            try:
                text = page.evaluate("document.querySelector('#main-container') ? document.querySelector('#main-container').innerText : ''")
                if text and len(text) > 10:
                    print(f"After {i+1}s - text: {text[:200]}")
                    break
            except Exception:
                pass
        else:
            text = page.evaluate("document.querySelector('#main-container') ? document.querySelector('#main-container').innerText : 'EMPTY'")
            print(f"After 30s - text: '{text[:200]}'")
        
        # Check URL
        url = page.evaluate("window.location.href")
        print(f"URL: {url}")
        
        page.close()
        context.close()

main()

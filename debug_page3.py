"""Debug: get the raw HTML of the AWS device page."""
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
        
        time.sleep(10.0)
        
        html = page.evaluate("document.documentElement.outerHTML")
        print(f"HTML length: {len(html)}")
        print(f"HTML:\n{html[:2000]}")
        
        url = page.evaluate("window.location.href")
        print(f"\nURL: {url}")
        
        page.close()
        context.close()

main()

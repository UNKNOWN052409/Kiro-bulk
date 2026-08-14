"""Debug: wait for page to fully load."""
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
        
        # Wait for page to complete loading
        for i in range(60):
            time.sleep(1.0)
            try:
                ready = page.evaluate("document.readyState")
                if ready == 'complete':
                    print(f"Page complete after {i+1}s")
                    break
            except Exception:
                pass
        else:
            ready = page.evaluate("document.readyState")
            print(f"Page still '{ready}' after 60s")
        
        # Now check content
        text = page.evaluate("document.body ? document.body.innerText : ''")
        print(f"Body text: '{text[:300]}'")
        
        url = page.evaluate("window.location.href")
        print(f"URL: {url}")
        
        page.close()
        context.close()

main()

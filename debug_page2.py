"""Debug: check what's on the AWS device page with commit wait."""
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
        except Exception as e:
            print(f"Goto error: {e}")
        
        # Wait longer for the page to fully load
        for i in range(15):
            time.sleep(1.0)
            try:
                text = page.evaluate("document.body ? document.body.innerText : ''")
                if text and len(text) > 20:
                    print(f"Body text (len={len(text)}): {text[:200]}")
                    break
            except Exception as e:
                pass
        else:
            try:
                text = page.evaluate("document.body ? document.body.innerText : ''")
                print(f"Body text after 15s: '{text[:100]}'")
                html_len = page.evaluate("document.documentElement.innerHTML.length")
                print(f"HTML length: {html_len}")
            except Exception as e:
                print(f"Final eval error: {e}")
        
        page.close()
        context.close()

main()

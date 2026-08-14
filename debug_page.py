"""Debug: check what's on the AWS device page."""
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto('https://view.awsapps.com/start/#/device?user_code=TEST-TEST',
                  wait_until='load', timeout=30000)
        time.sleep(8.0)
        
        # Try different ways to get content
        title = page.evaluate("document.title")
        html_len = page.evaluate("document.documentElement.innerHTML.length")
        body_len = page.evaluate("document.body ? document.body.innerHTML.length : 0")
        text = page.evaluate("document.body ? document.body.innerText : ''")
        
        print(f"Title: {title}")
        print(f"HTML length: {html_len}")
        print(f"Body innerHTML length: {body_len}")
        print(f"Body innerText length: {len(text)}")
        print(f"Body text: {text[:200]}")
        
        # Check iframes
        frames = page.frames
        print(f"\nFrames: {len(frames)}")
        for f in frames:
            print(f"  - {f.url[:80]}")
        
        page.close()
        context.close()

main()

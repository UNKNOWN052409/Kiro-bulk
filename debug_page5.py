"""Debug: check if the SPA scripts are loading."""
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        # Collect console messages
        messages = []
        page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: messages.append(f"PAGE ERROR: {err}"))
        
        try:
            page.goto('https://view.awsapps.com/start/#/device?user_code=TEST-TEST',
                      wait_until='commit', timeout=30000)
        except Exception:
            pass
        
        time.sleep(15.0)
        
        # Check various things
        checks = {
            'url': page.evaluate("window.location.href"),
            'mainContainer': page.evaluate("document.querySelector('#main-container') ? 'EXISTS' : 'MISSING'"),
            'mainContainerHTML': page.evaluate("document.querySelector('#main-container') ? document.querySelector('#main-container').innerHTML.length : 0"),
            'scripts': page.evaluate("document.querySelectorAll('script').length"),
            'bodyChildren': page.evaluate("document.body.children.length"),
            'readyState': page.evaluate("document.readyState"),
        }
        
        for k, v in checks.items():
            print(f"{k}: {v}")
        
        if messages:
            print(f"\nConsole messages ({len(messages)}):")
            for m in messages[:10]:
                print(f"  {m[:150]}")
        
        page.close()
        context.close()

main()

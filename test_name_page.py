from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    )
    context = browser.new_context(viewport={'width': 1280, 'height': 720})
    page = context.new_page()
    
    # Navigate to the OIDC authorize URL to trigger the flow
    # First, let's just navigate to profile.aws.amazon.com directly
    page.goto('https://profile.aws.amazon.com/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(10)
    
    # Check what's on the page
    body = page.evaluate("() => document.body ? document.body.innerText : 'NO BODY'")
    print(f"Body: {body[:500]}")
    
    # Also check with innerHTML length
    html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
    print(f"HTML length: {html_len}")
    
    browser.close()

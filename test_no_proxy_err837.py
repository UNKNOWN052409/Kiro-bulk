from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    )
    context = browser.new_context(viewport={'width': 1280, 'height': 720})
    page = context.new_page()
    
    # Go directly to the sign-in page (this is what OIDC redirects to)
    page.goto('https://us-east-1.signin.aws/platform/d-9067642ac7/login', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    print(f"Body: {body[:500]}")
    
    browser.close()

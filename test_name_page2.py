from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,  # Non-headless with Xvfb
        args=[
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1280,720',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        ],
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    )
    page = context.new_page()
    
    page.goto('https://profile.aws.amazon.com/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(15)
    
    body = page.evaluate("() => document.body ? document.body.innerText : 'NO BODY'")
    print(f"Body: {body[:500]}")
    
    html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
    print(f"HTML length: {html_len}")
    
    # Check readyState
    ready = page.evaluate("() => document.readyState")
    print(f"ReadyState: {ready}")
    
    browser.close()

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--proxy-server=socks5://127.0.0.1:10800',
        ],
    )
    context = browser.new_context(viewport={'width': 1280, 'height': 720})
    page = context.new_page()
    
    # Navigate to profile.aws.amazon.com with proxy
    page.goto('https://profile.aws.amazon.com/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(20)
    
    body = page.evaluate("() => document.body ? document.body.innerText : 'NO BODY'")
    print(f"Body: {body[:500]}")
    
    html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
    print(f"HTML length: {html_len}")
    
    # Check IP
    page.goto('https://ipinfo.io/json', wait_until='domcontentloaded', timeout=15000)
    time.sleep(2)
    ip_info = page.evaluate("() => document.body.innerText")
    print(f"IP: {ip_info[:100]}")
    
    browser.close()

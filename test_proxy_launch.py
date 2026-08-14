from playwright.sync_api import sync_playwright
import time

# Test: proxy via launch() proxy parameter
print("Test: Proxy via launch() proxy parameter")
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        proxy={'server': 'socks5://127.0.0.1:10800'},
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    )
    context = browser.new_context()
    page = context.new_page()
    page.goto('https://ipinfo.io/json', wait_until='domcontentloaded', timeout=15000)
    time.sleep(2)
    print(f"  IP: {page.evaluate('() => document.body.innerText')[:200]}")
    browser.close()

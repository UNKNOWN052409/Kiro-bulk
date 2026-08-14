from playwright.sync_api import sync_playwright
import time

# Test 1: Proxy via args
print("Test 1: Proxy via Chrome args")
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
    context = browser.new_context()
    page = context.new_page()
    page.goto('https://ipinfo.io/json', wait_until='domcontentloaded', timeout=15000)
    time.sleep(2)
    print(f"  Page: {page.evaluate('() => document.body.innerText')[:200]}")
    browser.close()

# Test 2: Proxy via Playwright context proxy param
print("\nTest 2: Proxy via Playwright proxy param")
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    )
    context = browser.new_context(
        proxy={'server': 'socks5://127.0.0.1:10800'},
    )
    page = context.new_page()
    page.goto('https://ipinfo.io/json', wait_until='domcontentloaded', timeout=15000)
    time.sleep(2)
    print(f"  Page: {page.evaluate('() => document.body.innerText')[:200]}")
    browser.close()

print("\nDone!")

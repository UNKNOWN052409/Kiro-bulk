from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        proxy={'server': 'socks5://127.0.0.1:10800'},
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='America/New_York',
    )
    page = context.new_page()
    
    # Navigate with no wait_until (let it load at its own pace)
    try:
        page.goto('https://profile.aws.amazon.com/', timeout=120000)
    except:
        pass
    
    # Wait up to 90 seconds
    for i in range(30):
        time.sleep(3)
        ready = page.evaluate("() => document.readyState")
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
        print(f"  [{i*3}s] readyState={ready} body_len={len(body)} html_len={html_len}")
        if len(body) > 100:
            print(f"\n  SUCCESS! Body: {body[:200]}")
            break
    
    browser.close()

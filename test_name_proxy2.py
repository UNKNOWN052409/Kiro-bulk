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
    
    # Navigate with longer timeout, no wait_until
    try:
        page.goto('https://profile.aws.amazon.com/', timeout=60000)
    except:
        pass
    
    # Wait and poll
    for i in range(30):
        time.sleep(3)
        ready = page.evaluate("() => document.readyState")
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
        print(f"  [{i*3}s] readyState={ready} body_len={len(body)} html_len={html_len} url={page.url[:80]}")
        if len(body) > 100:
            print(f"\n  SUCCESS! Body: {body[:300]}")
            break
    
    browser.close()

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    print(f"Pages: {len(context.pages)}")
    for i, page in enumerate(context.pages):
        try:
            body = page.evaluate("document.body.innerText")
            print(f"\nPage {i}: {page.url[:100]}")
            print(f"  Body: {body[:150]}")
        except Exception as e:
            print(f"\nPage {i}: Error - {e}")
    context.close()

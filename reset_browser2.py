from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    
    print(f"Contexts: {len(browser.contexts)}")
    
    # Try to use existing context
    context = browser.contexts[0]
    print(f"Pages: {len(context.pages)}")
    
    if context.pages:
        page = context.pages[0]
        try:
            page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
            time.sleep(2)
            print(f"Reset URL: {page.url}")
        except Exception as e:
            print(f"Error navigating: {e}")
            # Try to close the page and create new
            try:
                page.close()
                time.sleep(1)
                page = context.new_page()
                page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
                print(f"New page URL: {page.url}")
            except Exception as e2:
                print(f"Error creating new page: {e2}")
                # Close context and create new
                context.close()
                time.sleep(1)
                context = browser.new_context()
                page = context.new_page()
                page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
                print(f"Fresh context URL: {page.url}")
    else:
        page = context.new_page()
        page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
        print(f"New page URL: {page.url}")
    
    # Close context
    context.close()
    print("Done!")

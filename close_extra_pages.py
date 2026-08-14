"""Close all extra browser pages, keep only one."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    pages = context.pages
    print(f"[*] Found {len(pages)} pages")
    
    # Keep the first page, close the rest
    for page in pages[1:]:
        try:
            page.close()
            print(f"  Closed: {page.url[:60]}")
        except:
            pass
    
    remaining = context.pages
    print(f"\n[+] {len(remaining)} pages remaining")
    context.close()

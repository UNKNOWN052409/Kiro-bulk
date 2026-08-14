"""Logout from the existing AWS session."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    # Try to navigate to the SSO portal to find sign out
    page = context.new_page()
    
    print("[*] Navigating to SSO portal...")
    page.goto('https://view.awsapps.com/start', wait_until='domcontentloaded', timeout=30000)
    
    # Wait for render
    for i in range(60):
        time.sleep(2)
        try:
            ready = page.evaluate("document.readyState")
            if ready == 'complete':
                body = page.evaluate("document.body ? document.body.innerText : ''")
                if len(body) > 50:
                    print(f"  Body: {body[:200]}")
                    break
        except:
            pass
    
    # Try to find and click Sign out
    try:
        signout = page.get_by_role("button", name="Sign out", exact=True)
        if signout.is_visible(timeout=3000):
            signout.click(timeout=5000)
            print("[+] Clicked Sign out")
            time.sleep(5)
        else:
            print("[-] Sign out not visible")
    except:
        print("[-] No Sign out button found")
    
    # Check current state
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] After logout attempt:")
    print(f"    {body[:200]}")
    
    page.close()
    context.close()

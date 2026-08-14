"""Test logging out - check page structure."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='networkidle', timeout=30000)
    time.sleep(8)
    
    # Get all links and buttons
    links = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.textContent.trim()).filter(t => t).join(' | ')")
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.textContent.trim()).filter(t => t).join(' | ')")
    print(f"Links: {links[:300]}")
    print(f"Buttons: {buttons[:300]}")
    
    # Try clicking sign out
    try:
        page.locator('text=Sign out').first.click(timeout=5000)
        print("[+] Sign out clicked!")
        time.sleep(5)
    except Exception as e:
        print(f"[!] Error: {e}")
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"Body: {body[:300]}")
    
    page.close()
    context.close()

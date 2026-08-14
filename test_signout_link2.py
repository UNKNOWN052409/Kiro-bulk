"""Find the Sign out link on the SSO portal - with proper wait."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='networkidle', timeout=30000)
    time.sleep(10)
    
    # Dismiss cookies first
    for btn_text in ["Decline", "Dismiss"]:
        try:
            btns = page.locator(f'button:has-text("{btn_text}")').all()
            for btn in btns:
                try:
                    if btn.is_visible(timeout=500):
                        btn.click(timeout=1000)
                        time.sleep(0.5)
                except:
                    pass
        except:
            pass
    time.sleep(3)
    
    # Get current URL
    print(f"URL: {page.url}")
    
    # Get body
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"Body: {body[:300]}")
    
    # Get all links
    links = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => ({text: a.textContent.trim(), href: a.href}))")
    for link in links:
        if link['text']:
            print(f"  Link: '{link['text'][:30]}' -> {link['href'][:80]}")
    
    page.close()
    context.close()

"""Find the Sign out link on the SSO portal."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)
    
    # Get all elements that might be sign out
    elements = page.evaluate("""
        Array.from(document.querySelectorAll('a, button, [role="button"]'))
            .map(el => ({tag: el.tagName, text: el.textContent.trim().substring(0, 30), href: el.href || ''}))
            .filter(el => el.text.toLowerCase().includes('sign') || el.text.toLowerCase().includes('out') || el.text.toLowerCase().includes('logout'))
    """)
    print(f"Sign out elements: {elements}")
    
    # Also get all hrefs
    hrefs = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h).join('\\n')")
    print(f"\nAll hrefs:\n{hrefs[:1000]}")
    
    page.close()
    context.close()

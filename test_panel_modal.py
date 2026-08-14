"""Test if the panel's own modal browser flow works (might use different config)."""
import time
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        # Login to panel
        page.goto('https://ourproxy.sryze.cc', wait_until='commit', timeout=30000)
        time.sleep(3.0)
        page.evaluate("""async () => {
            await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password:'7894561230'})});
        }""")
        time.sleep(2.0)
        
        # Navigate to Kiro provider dashboard
        page.goto('https://ourproxy.sryze.cc/dashboard/providers/kiro', wait_until='commit', timeout=30000)
        time.sleep(5.0)
        
        # Wait for page to fully load
        for i in range(15):
            time.sleep(2.0)
            count = page.evaluate("document.querySelectorAll('button').length")
            if count > 500:
                print(f"Page loaded: {count} buttons")
                break
        
        # Get page text to find the Add button
        body_text = page.evaluate("document.body.innerText")
        
        # Look for add-related text
        import re
        add_matches = re.findall(r'.{30}add.{30}', body_text, re.IGNORECASE)
        print(f"Add context matches: {add_matches[:5]}")
        
        # Look for "Import" or other action buttons
        import_matches = re.findall(r'.{30}import.{30}', body_text, re.IGNORECASE)
        print(f"Import context matches: {import_matches[:5]}")
        
        # Look for "connect" 
        conn_matches = re.findall(r'.{30}connect.{30}', body_text, re.IGNORECASE)
        print(f"Connect context matches: {conn_matches[:5]}")
        
        # Show a broader section of the page text
        print(f"\n--- Page text (first 2000 chars) ---")
        print(body_text[:2000])
        
        page.close()
        context.close()

main()

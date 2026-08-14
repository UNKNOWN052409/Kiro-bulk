#!/usr/bin/env python3
"""Check the Kiro provider page on the panel."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    context = browser.contexts[0]
    page = context.new_page()
    
    # Login to panel
    page.goto('https://ourproxy.sryze.cc', wait_until='networkidle', timeout=30000)
    time.sleep(2)
    
    # Login via fetch
    r = page.evaluate("""async () => {
        const res = await fetch('/api/auth/login', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({password:'7894561230'})
        });
        return {ok: res.ok, status: res.status};
    }""")
    print(f'Login: {r}')
    time.sleep(2)
    
    # Navigate to kiro provider page
    page.goto('https://ourproxy.sryze.cc/dashboard/providers/kiro', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    print(f'URL: {page.url}')
    print(f'Title: {page.title()}')
    
    # Check button count
    button_count = page.evaluate("() => document.querySelectorAll('button').length")
    print(f'Buttons: {button_count}')
    
    page.screenshot(path='/tmp/kiro_provider_page.png')
    page.close()

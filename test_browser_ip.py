#!/usr/bin/env python3
"""Test what IP the browser sees using Playwright's native SOCKS5 proxy (no auth)."""
from playwright.sync_api import sync_playwright
import json

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        # Use Playwright's native SOCKS5 proxy support (no auth - bridge handles it)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            proxy={'server': 'socks5://127.0.0.1:10800'}
        )
        page = context.new_page()
        
        # Navigate to IP check
        try:
            page.goto('https://api.ipquery.io/?format=json', wait_until='domcontentloaded', timeout=30000)
            body_text = page.inner_text('body')
            print(f"Browser sees IP response: {body_text[:300]}")
            
            try:
                data = json.loads(body_text)
                print(f"\nIP: {data.get('ip', 'N/A')}")
                print(f"ISP: {data.get('isp', {}).get('org', 'N/A')}")
                print(f"Country: {data.get('location', {}).get('country', 'N/A')}")
                print(f"Datacenter: {data.get('risk', {}).get('is_datacenter', 'N/A')}")
                print(f"Risk Score: {data.get('risk', {}).get('risk_score', 'N/A')}")
            except Exception as e:
                print(f"Could not parse JSON: {e}")
        except Exception as e:
            print(f"Navigation failed: {e}")
            # Try checkip
            try:
                page.goto('https://checkip.amazonaws.com/', wait_until='domcontentloaded', timeout=30000)
                ip_text = page.inner_text('body').strip()
                print(f"checkip.amazonaws.com: {ip_text}")
            except Exception as e2:
                print(f"checkip also failed: {e2}")
        
        browser.close()

if __name__ == '__main__':
    main()

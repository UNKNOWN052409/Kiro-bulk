"""Test different authorization URL formats."""
import sys, os, time, uuid, json
from playwright.sync_api import sync_playwright
import boto3

client = boto3.client('sso-oidc', region_name='us-east-1')

# Try different URL formats
urls_to_try = [
    # Format 1: Standard OAuth2 authorize
    f'https://view.awsapps.com/start/#/oauth2/authorize?client_id=test&redirect_uri=http://127.0.0.1:8901&response_type=code',
    # Format 2: With login hint
    f'https://view.awsapps.com/start/#/oauth2/authorize?client_id=test&redirect_uri=http://127.0.0.1:8901&response_type=code&prompt=login',
    # Format 3: Without hash
    f'https://view.awsapps.com/start/oauth2/authorize?client_id=test&redirect_uri=http://127.0.0.1:8901&response_type=code',
    # Format 4: SSO portal API endpoint
    f'https://portal.sso.us-east-1.amazonaws.com/oauth2/authorize?client_id=test&redirect_uri=http://127.0.0.1:8901&response_type=code',
]

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    for i, url in enumerate(urls_to_try):
        print(f"\n[*] Testing URL format {i+1}: {url[:100]}...")
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            time.sleep(5)
            body = page.evaluate("document.body ? document.body.innerText : ''")
            buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
            print(f"  Body (first 150): {body[:150]}")
            print(f"  Buttons: {buttons[:100]}")
        except Exception as e:
            print(f"  Error: {e}")
    
    page.close()
    context.close()

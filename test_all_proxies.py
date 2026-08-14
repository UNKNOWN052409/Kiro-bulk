#!/usr/bin/env python3
"""
Test ALL ProxyRise proxy types and regions against profile.aws.amazon.com API
to find which one bypasses ERR-837/TES.
"""

import requests, json, time, uuid, random, string, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

# Generate all proxy variants
proxy_variants = [
    # HTTP format
    ("HTTP-res-any", f"http://res-any:{API_KEY}@gw.proxyrise.com:443"),
    ("HTTP-res-US", f"http://res-US:{API_KEY}@gw.proxyrise.com:443"),
    ("HTTP-res-IN", f"http://res-IN:{API_KEY}@gw.proxyrise.com:443"),
    ("HTTP-res-GB", f"http://res-GB:{API_KEY}@gw.proxyrise.com:443"),
    ("HTTP-res-CA", f"http://res-CA:{API_KEY}@gw.proxyrise.com:443"),
    ("HTTP-res-DE", f"http://res-DE:{API_KEY}@gw.proxyrise.com:443"),
    # HTTPS format (TLS proxy mode)
    ("HTTPS-res-any", f"https://res-any:{API_KEY}@gw.proxyrise.com:443"),
    ("HTTPS-res-US", f"https://res-US:{API_KEY}@gw.proxyrise.com:443"),
    # SOCKS5 format
    ("SOCKS5-res-any", f"socks5://res-any:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-US", f"socks5://res-US:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-IN", f"socks5://res-IN:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-GB", f"socks5://res-GB:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-CA", f"socks5://res-CA:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-DE", f"socks5://res-DE:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-AU", f"socks5://res-AU:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-BR", f"socks5://res-BR:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-JP", f"socks5://res-JP:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-FR", f"socks5://res-FR:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-NL", f"socks5://res-NL:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-SG", f"socks5://res-SG:{API_KEY}@gw.proxyrise.com:443"),
    ("SOCKS5-res-MX", f"socks5://res-MX:{API_KEY}@gw.proxyrise.com:443"),
]

# Token callback server
tokens_captured = {}
class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/oauth/callback' in self.path:
            tokens_captured['code'] = 'test'
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            return
        self.send_response(404)
        self.end_headers()
    def log_message(self, format, *args):
        pass

print("="*70)
print("ProxyRise Proxy Test - All Types & Regions")
print("="*70)

results = []

for name, proxy_url in proxy_variants:
    # Step 1: Test basic connectivity
    ip = "?"
    location = "?"
    connected = False
    try:
        resp = requests.get('https://api.ipquery.io/?format=json', 
                           proxies={'https': proxy_url}, timeout=15)
        if resp.status_code == 200:
            ip_data = resp.json()
            ip = ip_data.get('ip', '?')
            city = ip_data.get('city', '?')
            country = ip_data.get('country_code', '?')
            isp = ip_data.get('isp', '?')
            location = f"{city}, {country}, {isp}"
            connected = True
    except Exception as e:
        pass
    
    if not connected:
        print(f"\n  [{name}] FAILED to connect")
        results.append({'name': name, 'connected': False, 'blocked': None, 'error': 'No connection'})
        continue
    
    print(f"\n  [{name}] IP={ip}, {location}")
    
    # Step 2: Test profile.aws.amazon.com API directly
    # This is the endpoint that returns ERR-837/TES BLOCKED
    test_url = 'https://profile.aws.amazon.com/api/get-config'
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Referer': 'https://profile.aws.amazon.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    blocked = None
    response_body = ""
    try:
        resp = requests.post(test_url, json={}, headers=headers,
                           proxies={'https': proxy_url}, timeout=30)
        response_body = resp.text[:200]
        if 'BLOCKED' in resp.text or 'TES' in resp.text:
            blocked = True
        else:
            blocked = False
    except Exception as e:
        response_body = f"ERROR: {str(e)[:100]}"
    
    status = "BLOCKED ✗" if blocked else "OK ✓"
    print(f"    get-config: HTTP {resp.status_code if 'resp' in dir() else 'ERR'} - {status}")
    if response_body:
        print(f"    Body: {response_body[:150]}")
    
    results.append({
        'name': name,
        'connected': connected,
        'ip': ip,
        'location': location,
        'blocked': blocked,
        'response': response_body
    })

# Summary
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
connected_count = sum(1 for r in results if r['connected'])
not_blocked = sum(1 for r in results if r['connected'] and r['blocked'] == False)
print(f"Total tested: {len(results)}")
print(f"Connected: {connected_count}")
print(f"NOT blocked by TES: {not_blocked}")
print(f"\nWorking proxies (connected AND not blocked):")
for r in results:
    if r['connected'] and r['blocked'] == False:
        print(f"  ✓ {r['name']}: {r['ip']} ({r['location']})")
print(f"\nConnected but blocked by TES:")
for r in results:
    if r['connected'] and r['blocked'] == True:
        print(f"  ✗ {r['name']}: {r['ip']} ({r['location']})")

# Save results
with open('/home/ubuntu/kiro-gen/proxy_test_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to proxy_test_results.json")

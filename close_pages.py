#!/usr/bin/env python3
"""Close all stale pages in Chrome via CDP."""
import json
import urllib.request

# Get all pages
with urllib.request.urlopen('http://localhost:9222/json/list') as f:
    pages = json.load(f)

print(f"Total pages: {len(pages)}")
for p in pages:
    page_id = p.get('id', '')
    if page_id:
        # Close all pages except chrome://newtab
        url = p.get('url', '')
        if 'newtab' not in url and 'chrome' not in url:
            try:
                urllib.request.urlopen(f'http://localhost:9222/json/close/{page_id}')
                print(f"  Closed: {url[:50]}")
            except Exception as e:
                print(f"  Failed to close: {e}")

# Verify
with urllib.request.urlopen('http://localhost:9222/json/list') as f:
    pages = json.load(f)
print(f"\nRemaining pages: {len(pages)}")

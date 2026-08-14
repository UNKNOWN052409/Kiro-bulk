#!/usr/bin/env python3
"""Check panel connections count and status."""
import json
import subprocess

TOKEN = open('/tmp/panel_cookies.txt').read().strip().split('\n')[-1].split('\t')[-1]

result = subprocess.run(
    ['curl', '-s', '-b', f'auth_token={TOKEN}', 
     'https://ourproxy.sryze.cc/api/connections',
     '-H', f'Authorization: Bearer {TOKEN}'],
    capture_output=True, text=True
)

try:
    data = json.loads(result.stdout)
    if isinstance(data, list):
        conns = data
    elif isinstance(data, dict):
        conns = data.get('connections', data.get('data', data.get('items', [])))
        if not conns and 'connection' in data:
            conns = [data['connection']]
    else:
        conns = []
    
    print(f"Total connections: {len(conns)}")
    kiro_conns = [c for c in conns if c.get('provider') == 'kiro']
    print(f"Kiro connections: {len(kiro_conns)}")
    
    for c in kiro_conns[-5:]:
        print(f"  {c.get('name', 'N/A')}: status={c.get('testStatus', 'N/A')}, email={c.get('email', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
    print(f"Raw output: {result.stdout[:200]}")

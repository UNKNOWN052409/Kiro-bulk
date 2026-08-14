"""
Find the exact body format for the execute POST call.
The key line is: fetch(t, {method:"post", headers:{"Content-Type":"application/json"}, body:JSON.stringify(n)})
We need to find what 'n' contains.
"""

import re

with open('/home/ubuntu/kiro-gen/signin_main.js', 'r') as f:
    js = f.read()

# Find the context around the key fetch call
target = 'body:JSON.stringify(n)'
positions = [m.start() for m in re.finditer(re.escape(target), js)]
print(f"Found {len(positions)} occurrences of 'body:JSON.stringify(n)'")

for i, pos in enumerate(positions):
    # Get a large context
    start = max(0, pos - 2000)
    end = min(len(js), pos + 500)
    ctx = js[start:end]
    
    print(f"\n{'='*80}")
    print(f"Context {i} (2000 chars before, 500 after):")
    print(f"{'='*80}")
    print(ctx)
    print()

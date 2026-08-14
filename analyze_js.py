"""
Analyze the signin JS bundle to find the /api/execute endpoint format and request structure.
"""

import re

with open('/home/ubuntu/kiro-gen/signin_main.js', 'r') as f:
    js = f.read()

print(f"JS size: {len(js)} bytes")

# Find /api/execute context
print("\n=== /api/execute context ===")
# Find all occurrences
positions = [m.start() for m in re.finditer('/api/execute', js)]
print(f"Found {len(positions)} occurrences")

# Show context around first few
for i, pos in enumerate(positions[:5]):
    start = max(0, pos - 200)
    end = min(len(js), pos + 300)
    print(f"\n--- Occurrence {i} ---")
    print(js[start:end])

# Look for POST method with /api/execute
print("\n=== POST patterns ===")
post_patterns = re.findall(r'fetch\(["\']\/api\/execute["\'][^)]*\)', js)
print(f"Fetch calls: {len(post_patterns)}")
for p in post_patterns[:5]:
    print(f"  {p[:200]}")

# Look for the execute API call format
print("\n=== Execute API call format ===")
# Search for patterns like: fetch('/api/execute', {method: 'POST', body: ...})
execute_calls = re.findall(r'fetch\(\s*["\']/api/execute["\']\s*,\s*\{([^}]+)\}', js)
print(f"Execute calls with options: {len(execute_calls)}")
for c in execute_calls[:5]:
    print(f"  {c[:300]}")

# Look for "execute" in context of GraphQL or mutations
print("\n=== GraphQL/mutation patterns ===")
graphql = re.findall(r'mutation\s+\w+', js)
print(f"Mutations: {len(graphql)}")
for g in graphql[:10]:
    print(f"  {g}")

# Look for "query" patterns
queries = re.findall(r'query\s+\w+', js)
print(f"Queries: {len(queries)}")
for q in queries[:10]:
    print(f"  {q}")

# Look for operationName patterns
op_names = re.findall(r'operationName:\s*["\'](\w+)["\']', js)
print(f"\nOperation names: {set(op_names[:20])}")

# Look for the main API interaction
print("\n=== Looking for the form submission logic ===")
# Search for patterns related to email submission
email_patterns = re.findall(r'["\'](email|username|loginEmail)["\']', js)
print(f"Email-related strings: {set(email_patterns)}")

# Search for workflowStateHandle usage
wsh_patterns = re.findall(r'workflowStateHandle[^;]{0,200}', js)
print(f"\nworkflowStateHandle usage: {len(wsh_patterns)}")
for w in wsh_patterns[:5]:
    print(f"  {w[:150]}")

# Look for the state machine transitions
print("\n=== State machine ===")
states = re.findall(r'["\'](EMAIL|PASSWORD|OTP|MFA|name|Name|nameEntry)["\']', js)
print(f"State names: {set(states)}")

# Look for the actual POST body format
print("\n=== POST body format ===")
body_patterns = re.findall(r'body:\s*(?:JSON\.stringify\()?\{([^}]+)\}', js)
print(f"Body patterns: {len(body_patterns)}")
for b in body_patterns[:10]:
    if 'email' in b.lower() or 'workflow' in b.lower():
        print(f"  {b[:200]}")

"""
View the full email submission request body (truncated the fingerprint).
"""

import json

with open('/home/ubuntu/kiro-gen/captured_api_call.json') as f:
    data = json.load(f)

req = data[3]
body = json.loads(req['post_data'])

# Truncate the fingerprint for readability
for inp in body.get('inputs', []):
    if 'fingerPrint' in inp:
        inp['fingerPrint'] = inp['fingerPrint'][:50] + "...[truncated]"

print(json.dumps(body, indent=2))

"""
Check the full email submission request body and response format.
"""

import json

with open('/home/ubuntu/kiro-gen/captured_api_call.json') as f:
    data = json.load(f)

# The email submission is the last request (index 3)
req = data[3]
body = json.loads(req['post_data'])

print("=== Full email submission request body ===")
print(json.dumps(body, indent=2))

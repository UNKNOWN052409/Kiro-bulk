"""
Find the exact request body format for the /platform/{dir}/api/execute endpoint.
"""

import re

with open('/home/ubuntu/kiro-gen/signin_main.js', 'r') as f:
    js = f.read()

# The execute endpoint is at /platform/{directoryId}/api/execute
# Let's find how the request is constructed

# Look for "execute" in context of service calls
print("=== Service definitions ===")
# From the earlier output, we saw:
# signInLogin:{endpoint:"",path:"/platform/api/execute",pathWithDirectoryId:function(e){return"/platform/"+e+"/api/execute"},httpMethod:r.POST}
# This means the pathWithDirectoryId adds the directory ID

# Let's find the Service enum/object
service_def = re.search(r'Service=\{([^}]+)\}', js)
if service_def:
    print(f"Service: {service_def.group(1)[:500]}")

# Look for the HTTP client that makes the execute call
print("\n=== HTTP client / fetch wrapper ===")
# Search for patterns that construct the API URL and make requests
url_construct = re.findall(r'pathWithDirectoryId\([^)]*\)[^;]{0,300}', js)
print(f"URL construction: {len(url_construct)}")
for u in url_construct[:5]:
    print(f"  {u[:200]}")

# Look for the actual HTTP request (axios, fetch, XMLHttpRequest)
print("\n=== HTTP request methods ===")
# Look for common HTTP libraries
for lib in ['axios', 'fetch(', 'XMLHttpRequest', 'http.get', 'http.post']:
    count = js.count(lib)
    print(f"  {lib}: {count} occurrences")

# The app might use a custom HTTP client. Let's look for the execute function
print("\n=== Execute function ===")
# Search for the function that calls the execute endpoint
exec_func = re.findall(r'function\s+\w*execute\w*\s*\([^)]*\)\s*\{[^}]{0,500}', js)
print(f"Execute functions: {len(exec_func)}")
for ef in exec_func[:3]:
    print(f"  {ef[:400]}")

# Look for Redux actions that trigger the execute call
print("\n=== Redux actions ===")
# The state machine uses Redux. Let's find the actions
actions = re.findall(r'StepActions\.(\w+)', js)
print(f"Step actions: {set(actions)}")

# Look for the email submission action
print("\n=== Email submission ===")
# Search for patterns related to submitting email
email_submit = re.findall(r'[^\n]*email[^\n]*submit[^\n]*', js, re.IGNORECASE)
print(f"Email submit patterns: {len(email_submit)}")
for es in email_submit[:5]:
    print(f"  {es[:200]}")

# Look for the request payload construction
print("\n=== Request payload ===")
# The execute API likely takes a JSON body with operation name and variables
payload_patterns = re.findall(r'\{[^}]*operationName[^}]*\}', js)
print(f"OperationName payloads: {len(payload_patterns)}")
for pp in payload_patterns[:5]:
    print(f"  {pp[:200]}")

# Look for variables/inputs in the payload
var_patterns = re.findall(r'\{[^}]*variables[^}]*\}', js)
print(f"\nVariables payloads: {len(var_patterns)}")
for vp in var_patterns[:5]:
    print(f"  {vp[:200]}")

# The signin.aws API is actually a custom RPC, not GraphQL
# Let's look for the exact body format
print("\n=== Looking for body construction ===")
# Search for patterns like: body: JSON.stringify({...})
body_strings = re.findall(r'JSON\.stringify\(\{[^}]+\}\)', js)
print(f"JSON.stringify calls: {len(body_strings)}")
for bs in body_strings[:10]:
    if len(bs) < 200:
        print(f"  {bs}")

# Let's look for the specific email input submission
print("\n=== Email input handling ===")
# The SPA uses Redux. The email is submitted via an action
# Let's find the reducer that handles email submission
email_reducer = re.findall(r'case\s+["\']([^"\']*email[^"\']*)["\']', js, re.IGNORECASE)
print(f"Email reducer cases: {email_reducer[:10]}")

# Look for the step IDs
step_ids = re.findall(r'STEP_ID\.(\w+)', js)
print(f"\nStep IDs: {set(step_ids)}")

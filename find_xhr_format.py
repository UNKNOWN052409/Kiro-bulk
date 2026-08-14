"""
Find the XHR implementation for the execute API.
"""

import re

with open('/home/ubuntu/kiro-gen/signin_main.js', 'r') as f:
    js = f.read()

# Find all XMLHttpRequest references
print("=== XMLHttpRequest references ===")
xhr_refs = re.findall(r'XMLHttpRequest[^;]{0,300}', js)
print(f"Total: {len(xhr_refs)}")
for xr in xhr_refs[:15]:
    print(f"  {xr[:200]}")

# Find the actual XHR send/implementation
print("\n=== XHR send patterns ===")
xhr_send = re.findall(r'[^\n]*\.send\([^)]*\)[^\n]*', js)
print(f"XHR send: {len(xhr_send)}")
for xs in xhr_send[:10]:
    print(f"  {xs[:200]}")

# Find the central HTTP service that makes the execute call
print("\n=== HTTP service implementation ===")
# Look for patterns that construct the full URL including the path
http_patterns = re.findall(r'[^\n]*(?:open|send|fetch)[^\n]*api[^\n]*', js, re.IGNORECASE)
print(f"HTTP+API patterns: {len(http_patterns)}")
for hp in http_patterns[:10]:
    print(f"  {hp[:200]}")

# The execute API is likely called via a service layer
# Let's find the service implementation
print("\n=== Service layer ===")
# Look for the executeStep function implementation
# It calls executeStep({request:t, service:n})
# The service n has signInLogin which points to /platform/{dir}/api/execute
# Let's find what happens when executeStep is called

# Look for the function that processes the request
exec_proc = re.findall(r'function\s*\w*\(e\)\{[^}]*executeStep[^}]{0,200}', js)
print(f"ExecuteStep processors: {len(exec_proc)}")
for ep in exec_proc[:5]:
    print(f"  {ep[:300]}")

# Let's look for the actual HTTP transport layer
print("\n=== Transport layer ===")
# Look for patterns that make HTTP requests
transport = re.findall(r'(?:new XMLHttpRequest|fetch\()[^)]{0,200}', js)
print(f"Transport calls: {len(transport)}")
for tc in transport[:10]:
    print(f"  {tc[:200]}")

# The signin.aws uses a micro-frontend architecture. 
# The actual API call might be in a separate module
# Let's look for the module that handles the execute endpoint
print("\n=== Module imports for execute ===")
# Look for the Service enum definition
service_enum = re.findall(r'Service=\{[^}]+\}', js)
print(f"Service enum: {len(service_enum)}")
for se in service_enum[:3]:
    print(f"  {se[:400]}")

# Look for the signInLogin service definition in detail
print("\n=== signInLogin service detail ===")
signin_svc = re.findall(r'signInLogin:\{[^}]+\}', js)
print(f"signInLogin service: {len(signin_svc)}")
for ss in signin_svc[:3]:
    print(f"  {ss}")

# Look for the HTTP method enum
http_method = re.findall(r'HttpMethod=\{[^}]+\}', js)
print(f"\nHttpMethod: {http_method[:2]}")

# Now let's find the actual request builder
print("\n=== Request builder ===")
# The request object passed to executeStep likely has: stepId, workflowStateHandle, inputData
# Let's find the request construction
req_patterns = re.findall(r'request:\{[^}]+\}', js)
print(f"Request objects: {len(req_patterns)}")
for rp in req_patterns[:10]:
    print(f"  {rp[:200]}")

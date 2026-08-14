"""
Find the exact fetch call format for the execute API endpoint.
"""

import re

with open('/home/ubuntu/kiro-gen/signin_main.js', 'r') as f:
    js = f.read()

# Find all fetch( calls with context
print("=== All fetch calls ===")
fetch_calls = re.findall(r'fetch\([^)]{0,300}\)', js)
print(f"Total fetch calls: {len(fetch_calls)}")
for fc in fetch_calls[:10]:
    print(f"  {fc[:250]}")

# Find the execute endpoint URL construction
print("\n=== Execute URL construction ===")
# We know pathWithDirectoryId returns "/platform/"+e+"/api/execute"
# Let's find where this is called with fetch
exec_url = re.findall(r'pathWithDirectoryId\([^)]*\)', js)
print(f"pathWithDirectoryId calls: {len(exec_url)}")
for eu in exec_url[:5]:
    print(f"  {eu}")

# Find the actual HTTP call that uses the execute endpoint
print("\n=== HTTP service call ===")
# The Service object has signInLogin with path /platform/api/execute
# Let's find the function that calls this service
# Look for patterns like: service.signInLogin or Service.SignInLogin
service_calls = re.findall(r'[^\n]*signInLogin[^\n]*', js)
print(f"signInLogin references: {len(service_calls)}")
for sc in service_calls[:5]:
    print(f"  {sc[:200]}")

# Look for the actual XHR/fetch implementation
print("\n=== XHR implementation ===")
xhr_impls = re.findall(r'new XMLHttpRequest\(\)[^}]{0,500}', js)
print(f"XHR implementations: {len(xhr_impls)}")
for xi in xhr_impls[:3]:
    print(f"  {xi[:300]}")

# The app likely has a central HTTP service. Let's find it.
print("\n=== Central HTTP service ===")
# Look for patterns that construct the full URL
url_patterns = re.findall(r'endpoint\s*[:=]\s*["\']([^"\']+)["\'][^,]{0,100}', js)
print(f"Endpoint patterns: {url_patterns[:10]}")

# Look for the base URL construction
base_url = re.findall(r'(?:baseUrl|basePath|apiBase)[^,;]{0,100}', js)
print(f"\nBase URL patterns: {base_url[:5]}")

# The key is to find what the execute API expects as body
# Let's look at the executeStep action
print("\n=== executeStep action ===")
exec_step = re.findall(r'executeStep[^;]{0,500}', js)
print(f"executeStep references: {len(exec_step)}")
for es in exec_step[:5]:
    print(f"  {es[:300]}")

# Look for the request body construction for the execute call
print("\n=== Request body for execute ===")
# The body likely includes stepId, workflowStateHandle, and input data
body_patterns = re.findall(r'\{[^{}]*stepId[^{}]*\}', js)
print(f"StepId body patterns: {len(body_patterns)}")
for bp in body_patterns[:10]:
    print(f"  {bp[:200]}")

# Look for the specific email submission body
print("\n=== Email submission body ===")
# The email is submitted as part of GET_IDENTITY_USER step
email_body = re.findall(r'GET_IDENTITY_USER[^}]{0,300}', js)
print(f"GET_IDENTITY_USER context: {len(email_body)}")
for eb in email_body[:5]:
    print(f"  {eb[:250]}")

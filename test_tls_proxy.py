"""Test TLS proxy mode with Python requests."""
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

PROXY_URL = "https://res-us:pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1@gw.proxyrise.com:443"

proxies = {
    "http": PROXY_URL,
    "https": PROXY_URL,
}

# Test 1: GET request through TLS proxy
print("Test 1: GET through TLS proxy...")
try:
    r = requests.get("https://api.ipquery.io/?format=json", proxies=proxies, verify=False, timeout=30)
    print(f"  Status: {r.status_code}")
    print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 2: GET with full URL in request line (forward proxy style)
print("\nTest 2: GET with absolute URL...")
try:
    r = requests.get("https://api.ipquery.io/?format=json", proxies=proxies, verify=False, timeout=30, 
                     headers={"Host": "api.ipquery.io"})
    print(f"  Status: {r.status_code}")
    print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 3: HTTP target through proxy
print("\nTest 3: HTTP target through TLS proxy...")
try:
    r = requests.get("http://api.ipquery.io/?format=json", proxies=proxies, verify=False, timeout=30)
    print(f"  Status: {r.status_code}")
    print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

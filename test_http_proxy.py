"""Test HTTP forward proxy on port 8080 - capture full response."""
import socket
import base64
import json

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
AUTH_BASIC = base64.b64encode(f'res-us:{API_KEY}'.encode()).decode()

def forward_request(target_url, host, auth=AUTH_BASIC):
    """Send a forward proxy request through port 8080."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect(('gw.proxyrise.com', 8080))
    
    request = (
        f"GET {target_url} HTTP/1.1\r\n"
        f"Proxy-Authorization: Basic {auth}\r\n"
        f"Host: {host}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    sock.sendall(request.encode())
    
    response = b''
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        except:
            break
    
    sock.close()
    return response.decode('utf-8', errors='ignore')

# Test 1: HTTPS target through HTTP proxy (forward mode)
print("=== Test 1: HTTPS target through forward proxy ===")
resp = forward_request('https://api.ipquery.io/?format=json', 'api.ipquery.io')
print(f"Full response:\n{resp}")

# Test 2: Check if we can reach AWS
print("\n=== Test 2: AWS target through forward proxy ===")
resp2 = forward_request('https://signin.aws.amazon.com/', 'signin.aws.amazon.com')
print(f"Status line: {resp2.split(chr(10))[0]}")
print(f"Body preview: {resp2[-200:]}")

# Test 3: Check IP through proxy
print("\n=== Test 3: Check what IP the proxy gives ===")
resp3 = forward_request('https://api.ipquery.io/?format=json', 'api.ipquery.io')
lines = resp3.split('\r\n\r\n', 1)
if len(lines) > 1:
    try:
        data = json.loads(lines[1])
        print(f"IP: {data.get('ip')}")
        print(f"ISP: {data.get('isp', {}).get('name')}")
        print(f"Location: {data.get('location', {}).get('country')}, {data.get('location', {}).get('city')}")
        print(f"Is proxy: {data.get('security', {}).get('is_proxy')}")
        print(f"Is datacenter: {data.get('security', {}).get('is_datacenter')}")
    except Exception as e:
        print(f"Parse error: {e}")
        print(f"Raw: {lines[1][:200]}")

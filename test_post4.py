"""Test POST variations through proxy."""
import socket
import select

PROXY_HOST = 'gw.proxyrise.com'
PROXY_PORT = 8080

def send_and_recv(request_bytes, timeout=15):
    """Send request and receive response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((PROXY_HOST, PROXY_PORT))
    sock.sendall(request_bytes)
    
    response = b''
    while True:
        ready, _, _ = select.select([sock], [], [], 5)
        if not ready:
            print("    Timeout (no more data)")
            break
        try:
            chunk = sock.recv(65536)
            if not chunk:
                print("    Connection closed")
                break
            response += chunk
        except Exception as e:
            print(f"    Error: {e}")
            break
    
    sock.close()
    return response

body = '{"stepId": "", "workflowStateHandle": "test-123", "data": {}}'

# Test 1: POST with Content-Length (standard)
print("Test 1: POST with Content-Length")
req1 = (
    "POST https://api.ipquery.io/ HTTP/1.1\r\n"
    "Host: api.ipquery.io\r\n"
    "Content-Type: application/json\r\n"
    f"Content-Length: {len(body)}\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{body}"
)
resp1 = send_and_recv(req1.encode())
print(f"  Response: {resp1[:100] if resp1 else 'EMPTY'}")

# Test 2: POST with chunked encoding
print("\nTest 2: POST with chunked encoding")
chunked_body = f"{len(body):X}\r\n{body}\r\n0\r\n\r\n"
req2 = (
    "POST https://api.ipquery.io/ HTTP/1.1\r\n"
    "Host: api.ipquery.io\r\n"
    "Content-Type: application/json\r\n"
    "Transfer-Encoding: chunked\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{chunked_body}"
)
resp2 = send_and_recv(req2.encode())
print(f"  Response: {resp2[:100] if resp2 else 'EMPTY'}")

# Test 3: POST with empty body
print("\nTest 3: POST with empty body")
req3 = (
    "POST https://api.ipquery.io/ HTTP/1.1\r\n"
    "Host: api.ipquery.io\r\n"
    "Content-Type: application/json\r\n"
    "Content-Length: 0\r\n"
    "Connection: close\r\n"
    "\r\n"
)
resp3 = send_and_recv(req3.encode())
print(f"  Response: {resp3[:100] if resp3 else 'EMPTY'}")

# Test 4: POST to httpbin with form data
print("\nTest 4: POST form data to httpbin")
form_body = 'stepId=start&workflowStateHandle=test-456'
req4 = (
    "POST https://httpbin.org/post HTTP/1.1\r\n"
    "Host: httpbin.org\r\n"
    "Content-Type: application/x-www-form-urlencoded\r\n"
    f"Content-Length: {len(form_body)}\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{form_body}"
)
resp4 = send_and_recv(req4.encode())
if resp4:
    text = resp4.decode('utf-8', errors='ignore')
    lines = text.split('\r\n\r\n', 1)
    status = lines[0].split('\r\n')[0] if lines else 'N/A'
    body_text = lines[1] if len(lines) > 1 else ''
    print(f"  Status: {status}")
    print(f"  Body: {body_text[:200]}")
else:
    print("  EMPTY")

# Test 5: Try GET with query params (simulating POST as GET)
print("\nTest 5: GET with JSON in query param")
import json
import urllib.parse
data = urllib.parse.quote(json.dumps({'stepId': '', 'workflowStateHandle': 'test-789', 'data': {}}))
req5 = (
    f"GET https://httpbin.org/get?payload={data} HTTP/1.1\r\n"
    "Host: httpbin.org\r\n"
    "Connection: close\r\n"
    "\r\n"
)
resp5 = send_and_recv(req5.encode())
if resp5:
    text = resp5.decode('utf-8', errors='ignore')
    lines = text.split('\r\n\r\n', 1)
    status = lines[0].split('\r\n')[0] if lines else 'N/A'
    body_text = lines[1] if len(lines) > 1 else ''
    print(f"  Status: {status}")
    print(f"  Body: {body_text[:200]}")
else:
    print("  EMPTY")

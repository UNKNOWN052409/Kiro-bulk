"""Test POST through proxy with detailed response analysis."""
import socket
import select
import json

PROXY_HOST = 'gw.proxyrise.com'
PROXY_PORT = 8080

def send_proxy_request(request_str, timeout=15):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((PROXY_HOST, PROXY_PORT))
    sock.sendall(request_str.encode())
    
    response = b''
    while True:
        ready, _, _ = select.select([sock], [], [], 5)
        if not ready:
            break
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            response += chunk
        except:
            break
    sock.close()
    return response

# Test 1: POST to httpbin with full debug
print("=== Test 1: POST to httpbin (full response) ===")
body = '{"test": "hello world", "foo": "bar"}'
req = (
    "POST https://httpbin.org/post HTTP/1.1\r\n"
    "Host: httpbin.org\r\n"
    "Content-Type: application/json\r\n"
    f"Content-Length: {len(body)}\r\n"
    "Accept: */*\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{body}"
)
resp = send_proxy_request(req)
if resp:
    text = resp.decode('utf-8', errors='ignore')
    print(f"  Response length: {len(text)}")
    # Print first 500 chars
    print(f"  Content: {text[:500]}")
else:
    print("  EMPTY - no response")

# Test 2: GET to httpbin (should work)
print("\n=== Test 2: GET to httpbin (control test) ===")
req2 = "GET https://httpbin.org/get HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n"
resp2 = send_proxy_request(req2)
if resp2:
    text2 = resp2.decode('utf-8', errors='ignore')
    print(f"  Response length: {len(text2)}")
    lines = text2.split('\r\n\r\n', 1)
    status = lines[0].split('\r\n')[0]
    print(f"  Status: {status}")
    if len(lines) > 1:
        body2 = lines[1]
        idx = body2.find('{')
        print(f"  Body: {body2[idx:idx+200]}")
else:
    print("  EMPTY")

# Test 3: POST to a different target (not behind Cloudflare)
print("\n=== Test 3: POST to httpbin.org/post with HTTP (not HTTPS) ===")
body3 = '{"test": "hello"}'
req3 = (
    "POST http://httpbin.org/post HTTP/1.1\r\n"
    "Host: httpbin.org\r\n"
    "Content-Type: application/json\r\n"
    f"Content-Length: {len(body3)}\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{body3}"
)
resp3 = send_proxy_request(req3, timeout=10)
if resp3:
    text3 = resp3.decode('utf-8', errors='ignore')
    print(f"  Response: {text3[:200]}")
else:
    print("  EMPTY")

# Test 4: Try POST with no content-length (just close connection after body)
print("\n=== Test 4: POST without Content-Length ===")
body4 = '{"test": "hello"}'
req4 = (
    "POST https://httpbin.org/post HTTP/1.1\r\n"
    "Host: httpbin.org\r\n"
    "Content-Type: application/json\r\n"
    "\r\n"
    f"{body4}"
)
resp4 = send_proxy_request(req4, timeout=10)
if resp4:
    text4 = resp4.decode('utf-8', errors='ignore')
    print(f"  Response: {text4[:200]}")
else:
    print("  EMPTY")

# Test 5: POST to AWS API directly
print("\n=== Test 5: POST to AWS API through proxy ===")
body5 = json.dumps({'stepId': '', 'workflowStateHandle': 'test-uuid-123', 'data': {}})
req5 = (
    "POST https://us-east-1.signin.aws/api/execute HTTP/1.1\r\n"
    "Host: us-east-1.signin.aws\r\n"
    "Content-Type: application/json\r\n"
    f"Content-Length: {len(body5)}\r\n"
    "Accept: application/json\r\n"
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{body5}"
)
resp5 = send_proxy_request(req5, timeout=15)
if resp5:
    text5 = resp5.decode('utf-8', errors='ignore')
    print(f"  Response length: {len(text5)}")
    print(f"  Response: {text5[:500]}")
else:
    print("  EMPTY - connection closed without response")

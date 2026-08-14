"""Debug POST through proxy - try different body formats."""
import socket
import base64
import json
import uuid

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
AUTH = base64.b64encode(f'res-us:{API_KEY}'.encode()).decode()

def test_post(url, host, body, content_type='application/json'):
    """Send a POST through the forward proxy."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect(('gw.proxyrise.com', 8080))
    
    request = (
        f"POST {url} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Proxy-Authorization: Basic {AUTH}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "Accept: application/json\r\n"
        "\r\n"
        f"{body}"
    )
    
    sock.sendall(request.encode())
    
    response = b''
    while True:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            response += chunk
        except Exception as e:
            print(f"  Read error: {e}")
            break
    
    sock.close()
    text = response.decode('utf-8', errors='ignore')
    return text

# Test 1: POST to httpbin.org (echo server) - simple test
print("=== Test 1: POST to httpbin.org ===")
body1 = '{"test": "hello"}'
resp1 = test_post('https://httpbin.org/post', 'httpbin.org', body1)
if resp1:
    lines = resp1.split('\r\n\r\n', 1)
    status = lines[0].split('\r\n')[0]
    body_part = lines[1] if len(lines) > 1 else ''
    print(f"  Status: {status}")
    print(f"  Body: {body_part[:200]}")
else:
    print("  Empty response!")

# Test 2: POST to AWS with form-encoded body
print("\n=== Test 2: POST to AWS with form-encoded body ===")
body2 = 'stepId=&workflowStateHandle=test-123&data=%7B%7D'
resp2 = test_post(
    'https://us-east-1.signin.aws/api/execute',
    'us-east-1.signin.aws',
    body2,
    content_type='application/x-www-form-urlencoded'
)
if resp2:
    lines = resp2.split('\r\n\r\n', 1)
    status = lines[0].split('\r\n')[0]
    body_part = lines[1] if len(lines) > 1 else ''
    print(f"  Status: {status}")
    print(f"  Body: {body_part[:300]}")
else:
    print("  Empty response!")

# Test 3: POST to AWS with JSON body
print("\n=== Test 3: POST to AWS with JSON body ===")
body3 = json.dumps({
    'stepId': '',
    'workflowStateHandle': str(uuid.uuid4()),
    'data': {}
})
resp3 = test_post(
    'https://us-east-1.signin.aws/api/execute',
    'us-east-1.signin.aws',
    body3,
    content_type='application/json'
)
if resp3:
    lines = resp3.split('\r\n\r\n', 1)
    status = lines[0].split('\r\n')[0]
    body_part = lines[1] if len(lines) > 1 else ''
    print(f"  Status: {status}")
    print(f"  Body: {body_part[:300]}")
else:
    print("  Empty response!")

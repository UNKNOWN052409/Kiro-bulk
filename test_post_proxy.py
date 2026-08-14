"""Test POST through HTTP forward proxy to AWS API."""
import socket
import base64
import json

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
AUTH = base64.b64encode(f'res-us:{API_KEY}'.encode()).decode()

# Build a test POST request to the AWS execute API
workflow_id = str(__import__('uuid').uuid4())
test_body = json.dumps({
    'stepId': '',
    'workflowStateHandle': workflow_id,
    'data': {}
})

request = (
    f"POST https://us-east-1.signin.aws/api/execute HTTP/1.1\r\n"
    f"Host: us-east-1.signin.aws\r\n"
    f"Proxy-Authorization: Basic {AUTH}\r\n"
    "Content-Type: application/json\r\n"
    f"Content-Length: {len(test_body)}\r\n"
    "Connection: close\r\n"
    "Accept: application/json\r\n"
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36\r\n"
    "\r\n"
    f"{test_body}"
)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30)
sock.connect(('gw.proxyrise.com', 8080))
sock.sendall(request.encode())

response = b''
while True:
    try:
        chunk = sock.recv(65536)
        if not chunk:
            break
        response += chunk
    except:
        break

sock.close()

text = response.decode('utf-8', errors='ignore')
print(f"Raw response ({len(text)} bytes):")
print(text[:500])
print("---")
# Also print hex of first 200 bytes
print(f"Hex: {response[:200].hex()}")

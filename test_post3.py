"""Debug raw socket POST to understand the issue."""
import socket

# Connect and send a simple GET first to verify connection works
print("=== Test: Simple GET through proxy ===")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30)
sock.connect(('gw.proxyrise.com', 8080))

request = "GET https://api.ipquery.io/?format=json HTTP/1.1\r\nHost: api.ipquery.io\r\nConnection: close\r\n\r\n"
sock.sendall(request.encode())

response = b''
while True:
    try:
        chunk = sock.recv(65536)
        if not chunk:
            break
        response += chunk
        print(f"  Received {len(chunk)} bytes")
    except Exception as e:
        print(f"  Error: {e}")
        break

sock.close()
print(f"  Total: {len(response)} bytes")
print(f"  First 100 chars: {response[:100]}")

# Now try POST
print("\n=== Test: POST through proxy ===")
sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock2.settimeout(30)
sock2.connect(('gw.proxyrise.com', 8080))

body = '{"stepId": "", "workflowStateHandle": "test", "data": {}}'
request2 = (
    "POST https://us-east-1.signin.aws/api/execute HTTP/1.1\r\n"
    "Host: us-east-1.signin.aws\r\n"
    "Content-Type: application/json\r\n"
    f"Content-Length: {len(body)}\r\n"
    "Connection: close\r\n"
    "\r\n"
    f"{body}"
)
print(f"  Sending {len(request2)} bytes...")
sock2.sendall(request2.encode())
print("  Sent!")

response2 = b''
import select
while True:
    ready, _, _ = select.select([sock2], [], [], 10)
    if not ready:
        print("  Timeout waiting for response")
        break
    chunk = sock2.recv(65536)
    if not chunk:
        print("  Connection closed by server")
        break
    response2 += chunk
    print(f"  Received {len(chunk)} bytes")

sock2.close()
print(f"  Total: {len(response2)} bytes")
if response2:
    print(f"  First 200 chars: {response2[:200]}")

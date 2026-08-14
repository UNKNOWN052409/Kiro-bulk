"""Test TLS proxy mode - send HTTPS request through port 443."""
import socket
import ssl
import base64

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

def try_tls_proxy(auth_header=None, host_header=None):
    """Try TLS proxy mode with various configurations."""
    PROXY_HOST = 'gw.proxyrise.com'
    PROXY_PORT = 443
    TARGET_URL = 'https://api.ipquery.io/?format=json'
    TARGET_HOST = 'api.ipquery.io'
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(20)
        sock.connect((PROXY_HOST, PROXY_PORT))
        
        # SSL wrap - the proxy presents its own cert
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(sock, server_hostname=PROXY_HOST)
        
        # Build request
        request = f"GET {TARGET_URL} HTTP/1.1\r\n"
        request += f"Host: {host_header or TARGET_HOST}\r\n"
        if auth_header:
            request += f"Proxy-Authorization: Basic {auth_header}\r\n"
        request += "Connection: close\r\n\r\n"
        
        ssl_sock.sendall(request.encode())
        
        response = b''
        while True:
            try:
                chunk = ssl_sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except:
                break
        
        ssl_sock.close()
        text = response.decode('utf-8', errors='ignore')
        return text[:200]
        
    except Exception as e:
        return f"Error: {e}"

# Test different auth formats
AUTH_US = base64.b64encode(f'res-us:{API_KEY}'.encode()).decode()
AUTH_ANY = base64.b64encode(f'res-any:{API_KEY}'.encode()).decode()

print("=== Test 1: res-us auth, target host header ===")
print(try_tls_proxy(AUTH_US, 'api.ipquery.io'))

print("\n=== Test 2: res-any auth, target host header ===")
print(try_tls_proxy(AUTH_ANY, 'api.ipquery.io'))

print("\n=== Test 3: res-us auth, proxy host header ===")
print(try_tls_proxy(AUTH_US, 'gw.proxyrise.com'))

print("\n=== Test 4: No auth, target host header ===")
print(try_tls_proxy(None, 'api.ipquery.io'))

print("\n=== Test 5: res-us auth, no host header ===")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect(('gw.proxyrise.com', 443))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ssl_sock = ctx.wrap_socket(sock, server_hostname='gw.proxyrise.com')
    request = f"GET https://api.ipquery.io/?format=json HTTP/1.1\r\nProxy-Authorization: Basic {AUTH_US}\r\nConnection: close\r\n\r\n"
    ssl_sock.sendall(request.encode())
    response = b''
    while True:
        try:
            chunk = ssl_sock.recv(4096)
            if not chunk:
                break
            response += chunk
        except:
            break
    ssl_sock.close()
    print(response.decode('utf-8', errors='ignore')[:200])
except Exception as e:
    print(f"Error: {e}")

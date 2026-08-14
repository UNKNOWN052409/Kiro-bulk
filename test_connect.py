"""Test CONNECT tunnel on port 8080 and HTTPS forward proxy on port 443."""
import socket
import ssl
import base64

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
AUTH = base64.b64encode(f'res-us:{API_KEY}'.encode()).decode()

# Test 1: CONNECT on port 8080
print("=== Test 1: CONNECT tunnel on port 8080 ===")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect(('gw.proxyrise.com', 8080))
    
    request = f"CONNECT api.ipquery.io:443 HTTP/1.1\r\nHost: api.ipquery.io:443\r\nProxy-Authorization: Basic {AUTH}\r\n\r\n"
    sock.sendall(request.encode())
    
    response = b''
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\r\n\r\n' in response:
                break
        except:
            break
    
    text = response.decode('utf-8', errors='ignore')
    print(f"  CONNECT response: {text[:200]}")
    
    if '200' in text:
        print("  CONNECT successful! Trying SSL...")
        ctx = ssl.create_default_context()
        ssl_sock = ctx.wrap_socket(sock, server_hostname='api.ipquery.io')
        
        http_req = "GET /?format=json HTTP/1.1\r\nHost: api.ipquery.io\r\nConnection: close\r\n\r\n"
        ssl_sock.sendall(http_req.encode())
        
        resp = b''
        while True:
            try:
                chunk = ssl_sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
            except:
                break
        
        ssl_sock.close()
        body = resp.decode('utf-8', errors='ignore')
        # Find JSON body
        idx = body.find('{')
        if idx >= 0:
            print(f"  Response body: {body[idx:idx+200]}")
    
except Exception as e:
    print(f"  Error: {e}")

# Test 2: CONNECT on port 443 (TLS proxy mode - should work differently)
print("\n=== Test 2: CONNECT tunnel on port 443 ===")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect(('gw.proxyrise.com', 443))
    
    request = f"CONNECT api.ipquery.io:443 HTTP/1.1\r\nHost: api.ipquery.io:443\r\nProxy-Authorization: Basic {AUTH}\r\n\r\n"
    sock.sendall(request.encode())
    
    response = b''
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\r\n\r\n' in response:
                break
        except:
            break
    
    text = response.decode('utf-8', errors='ignore')
    print(f"  CONNECT response: {text[:200]}")
    
except Exception as e:
    print(f"  Error: {e}")

# Test 3: HTTPS forward proxy on port 443 (TLS proxy mode) - try different format
print("\n=== Test 3: TLS proxy mode - try without Proxy-Authorization header ===")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect(('gw.proxyrise.com', 443))
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ssl_sock = ctx.wrap_socket(sock, server_hostname='gw.proxyrise.com')
    
    # Try with username:password in URL format
    request = f"GET https://api.ipquery.io/?format=json HTTP/1.1\r\nHost: api.ipquery.io\r\nProxy-Authorization: Basic {AUTH}\r\nConnection: close\r\n\r\n"
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
    print(f"  Response: {text[:200]}")
    
except Exception as e:
    print(f"  Error: {e}")

# Test 4: Try res-any instead of res-us
print("\n=== Test 4: CONNECT on 8080 with res-any ===")
try:
    AUTH_ANY = base64.b64encode(f'res-any:{API_KEY}'.encode()).decode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect(('gw.proxyrise.com', 8080))
    
    request = f"CONNECT api.ipquery.io:443 HTTP/1.1\r\nHost: api.ipquery.io:443\r\nProxy-Authorization: Basic {AUTH_ANY}\r\n\r\n"
    sock.sendall(request.encode())
    
    response = b''
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\r\n\r\n' in response:
                break
        except:
            break
    
    text = response.decode('utf-8', errors='ignore')
    print(f"  CONNECT response: {text[:200]}")
    
except Exception as e:
    print(f"  Error: {e}")

"""Test different auth schemes for TLS proxy mode."""
import socket
import ssl
import base64

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

def try_tls_request(auth_scheme, auth_value, host_val):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(20)
        sock.connect(('gw.proxyrise.com', 443))
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(sock, server_hostname='gw.proxyrise.com')
        
        request = f"GET https://api.ipquery.io/?format=json HTTP/1.1\r\n"
        request += f"Host: {host_val}\r\n"
        if auth_scheme:
            request += f"Proxy-Authorization: {auth_scheme} {auth_value}\r\n"
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
        return response.decode('utf-8', errors='ignore')[:150]
    except Exception as e:
        return f"Error: {e}"

AUTH_BASIC = base64.b64encode(f'res-us:{API_KEY}'.encode()).decode()
AUTH_BEARER = API_KEY  # Try just the API key as bearer

# Test 1: Basic auth with res-us
print("1. Basic res-us:", try_tls_request("Basic", AUTH_BASIC, 'api.ipquery.io')[:100])

# Test 2: Bearer auth
print("2. Bearer API key:", try_tls_request("Bearer", AUTH_BEARER, 'api.ipquery.io')[:100])

# Test 3: Just API key without scheme
print("3. Raw API key:", try_tls_request("", AUTH_BEARER, 'api.ipquery.io')[:100])

# Test 4: Basic auth with just API key (no username)
AUTH_KEY_ONLY = base64.b64encode(f'{API_KEY}'.encode()).decode()
print("4. Basic API key only:", try_tls_request("Basic", AUTH_KEY_ONLY, 'api.ipquery.io')[:100])

# Test 5: Try username "residential" 
AUTH_RES = base64.b64encode(f'residential:{API_KEY}'.encode()).decode()
print("5. Basic residential:", try_tls_request("Basic", AUTH_RES, 'api.ipquery.io')[:100])

# Test 6: Try empty username
AUTH_EMPTY = base64.b64encode(f':{API_KEY}'.encode()).decode()
print("6. Basic empty user:", try_tls_request("Basic", AUTH_EMPTY, 'api.ipquery.io')[:100])

# Test 7: Try the HTTP proxy format that worked earlier (port 8080, HTTP target)
# But with HTTPS target through CONNECT on 8080
print("\n7. HTTP proxy port 8080 - forward HTTP request to HTTPS target:")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect(('gw.proxyrise.com', 8080))
    
    # Send HTTP request to HTTPS target through forward proxy
    request = (
        "GET https://api.ipquery.io/?format=json HTTP/1.1\r\n"
        f"Proxy-Authorization: Basic {AUTH_BASIC}\r\n"
        "Host: api.ipquery.io\r\n"
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
    text = response.decode('utf-8', errors='ignore')
    # Parse status
    lines = text.split('\r\n')
    print(f"   Status: {lines[0]}")
    if '200' in lines[0]:
        idx = text.find('{')
        if idx >= 0:
            print(f"   Body: {text[idx:idx+150]}")
    else:
        print(f"   Response: {text[:150]}")
except Exception as e:
    print(f"   Error: {e}")

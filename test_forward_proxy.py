"""Test ProxyRise forward proxy mode (not CONNECT tunnel)."""
import socket
import ssl

def test_forward_proxy():
    """Send a forward proxy request (full URL in request line)."""
    PROXY_HOST = 'gw.proxyrise.com'
    PROXY_PORT = 443
    API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
    
    # Test with HTTPS target through TLS proxy mode
    print("=== Test: TLS proxy mode (forward HTTPS request) ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((PROXY_HOST, PROXY_PORT))
        
        # SSL wrap for TLS proxy mode
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(sock, server_hostname=PROXY_HOST)
        
        # Send forward proxy request (full URL in request line)
        request = (
            "GET https://api.ipquery.io/?format=json HTTP/1.1\r\n"
            f"Proxy-Authorization: Basic {__import__('base64').b64encode(f'res-us:{API_KEY}'.encode()).decode()}\r\n"
            "Host: api.ipquery.io\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
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
        
        # Parse response
        text = response.decode('utf-8', errors='ignore')
        print(f"  Response: {text[:300]}")
        
    except Exception as e:
        print(f"  Error: {e}")

    # Test with HTTP target (non-SSL proxy)
    print("\n=== Test: HTTP proxy mode (forward HTTP request) ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((PROXY_HOST, 8080))  # Try common HTTP proxy port
        
        request = (
            "GET http://api.ipquery.io/?format=json HTTP/1.1\r\n"
            f"Proxy-Authorization: Basic {__import__('base64').b64encode(f'res-us:{API_KEY}'.encode()).decode()}\r\n"
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
        print(f"  Response: {text[:300]}")
        
    except Exception as e:
        print(f"  Error: {e}")

    # Test SOCKS5 with different target (maybe only certain hosts work)
    print("\n=== Test: SOCKS5 to AWS domain ===")
    try:
        import socks
        s = socks.socksocket()
        s.settimeout(20)
        s.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT, 
                    username='res-us', password=API_KEY)
        print("  Connecting to signin.aws.amazon.com:443...")
        s.connect(('signin.aws.amazon.com', 443))
        print("  Connected!")
        
        # SSL wrap
        ctx = ssl.create_default_context()
        ssl_sock = ctx.wrap_socket(s, server_hostname='signin.aws.amazon.com')
        
        request = (
            "GET / HTTP/1.1\r\n"
            "Host: signin.aws.amazon.com\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
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


if __name__ == '__main__':
    test_forward_proxy()

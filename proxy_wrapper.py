"""
Simple HTTP proxy wrapper that forwards to ProxyRise SOCKS5.
Listens on localhost:8899 and forwards all traffic through the SOCKS5 residential proxy.
"""

import socket
import threading
import socks
import sys

# ProxyRise config
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = sys.argv[1] if len(sys.argv) > 1 else '12345678'
LISTEN_PORT = 8899

# ProxyRise SOCKS5 endpoint
SOCKS5_HOST = 'gw.proxyrise.com'
SOCKS5_PORT = 443
SOCKS5_USER = f'res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}'


def handle_client(client_sock, client_addr):
    """Handle a single client connection through SOCKS5 proxy"""
    try:
        # Read the CONNECT request from the browser
        request = b''
        while b'\r\n\r\n' not in request:
            data = client_sock.recv(4096)
            if not data:
                return
            request += data
        
        request_str = request.decode('utf-8', errors='ignore')
        lines = request_str.split('\r\n')
        
        if not lines or not lines[0].startswith('CONNECT'):
            # Not a CONNECT request, close
            client_sock.close()
            return
        
        # Parse target host:port
        target = lines[0].split(' ')[1]
        if ':' in target:
            host, port = target.rsplit(':', 1)
            port = int(port)
        else:
            host = target
            port = 443
        
        print(f"  [PROXY] CONNECT {host}:{port}")
        
        # Connect through SOCKS5 to target
        s = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        s.set_proxy(socks.SOCKS5, SOCKS5_HOST, SOCKS5_PORT, 
                    username=f'res-us-sid-{PROXY_SESSION_ID}',
                    password=PROXYRISE_API_KEY)
        s.settimeout(30)
        s.connect((host, port))
        
        # Send 200 response to browser
        client_sock.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        
        # Bidirectional forwarding
        def forward(src, dst):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
            except:
                pass
            finally:
                try:
                    src.close()
                except:
                    pass
                try:
                    dst.close()
                except:
                    pass
        
        t1 = threading.Thread(target=forward, args=(client_sock, s), daemon=True)
        t2 = threading.Thread(target=forward, args=(s, client_sock), daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=120)
        t2.join(timeout=5)
        
    except Exception as e:
        print(f"  [PROXY] Error: {e}")
        try:
            client_sock.close()
        except:
            pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', LISTEN_PORT))
    server.listen(100)
    print(f"Local HTTP proxy on 127.0.0.1:{LISTEN_PORT}")
    print(f"Forwarding to SOCKS5: res-us-sid-{PROXY_SESSION_ID} @ {SOCKS5_HOST}:{SOCKS5_PORT}")
    
    while True:
        client_sock, client_addr = server.accept()
        print(f"[ACCEPT] {client_addr}")
        t = threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True)
        t.start()


if __name__ == '__main__':
    main()

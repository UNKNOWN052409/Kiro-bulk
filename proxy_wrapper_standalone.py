#!/usr/bin/env python3
"""
High-performance Local HTTP proxy wrapper v5.
Accepts HTTP CONNECT from local browser on port 8899.
Creates separate HTTPS (TLS) connections to ProxyRise for each tunnel.
Uses sticky session (res-us-sid-XXXXX) so all connections get the SAME IP.
"""

import socket
import threading
import ssl
import sys
import time
import base64
import select
import random

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXYRISE_HOST = 'gw.proxyrise.com'
PROXYRISE_PORT = 443

# Sticky session: same IP across all connections
SESSION = f'res-us-sid-{random.randint(100000, 999999999)}'

LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 8899


def create_tls_tunnel(target_host, target_port):
    """Create an HTTPS tunnel through ProxyRise to the target."""
    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.settimeout(90)
    
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    tls_sock = ctx.wrap_socket(raw_sock, server_hostname=PROXYRISE_HOST)
    tls_sock.settimeout(90)
    tls_sock.connect((PROXYRISE_HOST, PROXYRISE_PORT))
    
    auth = base64.b64encode(f'{SESSION}:{PROXYRISE_API_KEY}'.encode()).decode()
    request = (
        f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
        f"Host: {target_host}:{target_port}\r\n"
        f"Proxy-Authorization: Basic {auth}\r\n"
        f"Proxy-Connection: Keep-Alive\r\n"
        f"\r\n"
    )
    tls_sock.sendall(request.encode())
    
    # Read response
    resp = b''
    while b'\r\n\r\n' not in resp:
        chunk = tls_sock.recv(4096)
        if not chunk:
            raise Exception("Proxy connection closed without response")
        resp += chunk
        if len(resp) > 8192:
            break
    
    if b'200' not in resp.split(b'\r\n')[0]:
        raise Exception(f"CONNECT failed: {resp[:200]}")
    
    return tls_sock


def handle_https(client_socket, target_host, target_port):
    """Handle HTTPS CONNECT tunneling."""
    try:
        tls = create_tls_tunnel(target_host, target_port)
        client_socket.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
        
        def forward(src, dst, sock_a, sock_b):
            try:
                while True:
                    readable, _, _ = select.select([src], [], [src], 5)
                    if readable:
                        data = src.recv(65536)
                        if not data:
                            break
                        dst.sendall(data)
            except:
                pass
            finally:
                try:
                    sock_a.close()
                except:
                    pass
                try:
                    sock_b.close()
                except:
                    pass
        
        # Forward client->proxy and proxy->client
        t1 = threading.Thread(target=forward, args=(client_socket, tls, client_socket, tls), daemon=True)
        t2 = threading.Thread(target=forward, args=(tls, client_socket, tls, client_socket), daemon=True)
        t1.start()
        t2.start()
        
        # Wait for both to finish (connection is done)
        t1.join(timeout=300)
        t2.join(timeout=300)
        
    except Exception:
        try:
            client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
        except:
            pass
        try:
            client_socket.close()
        except:
            pass


def handle_http(client_socket, target_host, target_port, request):
    """Handle plain HTTP requests through the proxy."""
    try:
        tls = create_tls_tunnel(target_host, target_port)
        tls.sendall(request.encode())
        
        response = b''
        try:
            while True:
                data = tls.recv(65536)
                if not data:
                    break
                response += data
                if b'\r\n\r\n' in response:
                    header_end = response.find(b'\r\n\r\n')
                    headers = response[:header_end].decode('utf-8', errors='ignore')
                    content_length = None
                    transfer_encoding = ''
                    for hline in headers.split('\r\n'):
                        hl = hline.lower()
                        if hl.startswith('content-length:'):
                            content_length = int(hline.split(':')[1].strip())
                        elif hl.startswith('transfer-encoding:'):
                            transfer_encoding = hline.split(':')[1].strip().lower()
                    
                    if transfer_encoding == 'chunked':
                        while b'0\r\n\r\n' not in response[-200:]:
                            data = tls.recv(65536)
                            if not data:
                                break
                            response += data
                    elif content_length is not None:
                        body_start = header_end + 4
                        while len(response[body_start:]) < content_length:
                            data = tls.recv(min(65536, content_length - len(response[body_start:])))
                            if not data:
                                break
                            response += data
                    else:
                        tls.settimeout(3)
                        while True:
                            try:
                                data = tls.recv(65536)
                                if not data:
                                    break
                                response += data
                            except socket.timeout:
                                break
                        tls.settimeout(90)
                    break
        except Exception:
            pass
        
        client_socket.sendall(response)
        tls.close()
        client_socket.close()
    except Exception:
        try:
            client_socket.close()
        except:
            pass


def handle_client(client_socket):
    """Handle a single client connection."""
    try:
        client_socket.settimeout(60)
        request = b''
        try:
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request += chunk
                if b'\r\n\r\n' in request:
                    header_end = request.find(b'\r\n\r\n')
                    headers = request[:header_end].decode('utf-8', errors='ignore')
                    has_content_length = False
                    for line in headers.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            has_content_length = True
                            break
                    if not has_content_length:
                        break
                if len(request) > 8192:
                    break
        except socket.timeout:
            pass
        
        request = request.decode('utf-8', errors='ignore')
        lines = request.split('\r\n')
        
        target_host = ''
        target_port = 443
        is_connect = False
        
        if lines[0].startswith('CONNECT'):
            is_connect = True
            parts = lines[0].split(' ')
            target = parts[1].split(':')
            target_host = target[0]
            target_port = int(target[1]) if len(target) > 1 else 443
        else:
            for line in lines[1:]:
                if line.lower().startswith('host:'):
                    host = line.split(':', 1)[1].strip()
                    target = host.split(':')
                    target_host = target[0]
                    target_port = int(target[1]) if len(target) > 1 else 443
                    break
        
        if not target_host:
            client_socket.close()
            return
        
        if is_connect:
            handle_https(client_socket, target_host, target_port)
        else:
            handle_http(client_socket, target_host, target_port, request)
    except Exception:
        try:
            client_socket.close()
        except:
            pass


def main():
    global LISTEN_PORT, SESSION
    
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            LISTEN_PORT = int(sys.argv[i + 1])
        if arg == '--session' and i + 1 < len(sys.argv):
            base = sys.argv[i + 1]
            SESSION = f'{base}-sid-{random.randint(100000, 999999999)}'
    
    print(f"Proxy wrapper v5 listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    print(f"Session: {SESSION}", flush=True)
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(1024)
    
    while True:
        try:
            client, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client,), daemon=True)
            t.start()
        except Exception:
            pass


if __name__ == '__main__':
    main()

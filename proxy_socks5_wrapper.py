#!/usr/bin/env python3
"""
HTTPS proxy wrapper for ProxyRise.
Accepts HTTP CONNECT from local browser on port 8899.
Forwards traffic through ProxyRise HTTPS (TLS) gateway with sticky session.
Uses self-signed cert (proxy-insecure mode).
"""
import socket
import ssl
import threading
import sys
import select
import random
import base64
from collections import defaultdict

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXYRISE_HOST = 'gw.proxyrise.com'
PROXYRISE_PORT = 443

SESSION = f'res-us-sid-{random.randint(100000, 999999999)}'
USERNAME = SESSION
PASSWORD = PROXYRISE_API_KEY

LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 8899

# Connection pool: reuse TLS tunnels per client address + target
_connection_pool = {}
_pool_lock = threading.Lock()


def get_pooled_tunnel(client_key, target_host, target_port):
    """Get or create a TLS tunnel, reusing existing ones for the same client+target."""
    pool_key = (client_key, target_host, target_port)
    with _pool_lock:
        if pool_key in _connection_pool:
            tls = _connection_pool[pool_key]
            # Check if connection is still alive
            try:
                tls.setblocking(False)
                data = tls.recv(1, socket.MSG_PEEK)
                tls.setblocking(True)
                # Connection is alive, reuse it
                return tls
            except Exception:
                tls.setblocking(True)
                # Connection is dead, remove it
                del _connection_pool[pool_key]
    
    # Create new tunnel
    tls = create_https_tunnel(target_host, target_port)
    with _pool_lock:
        _connection_pool[pool_key] = tls
    return tls


def create_https_tunnel(target_host, target_port):
    """Connect to ProxyRise via TLS, authenticate, then CONNECT to target."""
    # Create raw socket to gateway
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(30)
    s.connect((PROXYRISE_HOST, PROXYRISE_PORT))
    
    # Wrap in TLS (skip certificate verification - self-signed cert)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    tls = ctx.wrap_socket(s, server_hostname=PROXYRISE_HOST)
    tls.settimeout(30)
    
    # Authenticate with Proxy-Authorization header
    auth = base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()
    connect_req = f'CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\nProxy-Authorization: Basic {auth}\r\n\r\n'
    tls.sendall(connect_req.encode())
    
    # Read response
    response = b''
    while b'\r\n\r\n' not in response:
        data = tls.recv(4096)
        if not data:
            raise Exception('Proxy connection closed')
        response += data
        if len(response) > 8192:
            break
    
    resp_str = response.decode('utf-8', errors='ignore')
    if '200' not in resp_str.split('\r\n')[0]:
        raise Exception(f'Proxy CONNECT failed: {resp_str[:100]}')
    
    return tls


def forward_data(src, dst):
    try:
        while True:
            readable, _, _ = select.select([src], [], [src], 10)
            if readable:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
    except Exception:
        pass


def handle_connect(client_socket, target_host, target_port):
    client_key = str(client_socket.getpeername())
    tls = get_pooled_tunnel(client_key, target_host, target_port)
    tls.settimeout(120)
    client_socket.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
    t1 = threading.Thread(target=forward_data, args=(client_socket, tls), daemon=True)
    t2 = threading.Thread(target=forward_data, args=(tls, client_socket), daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=300)
    t2.join(timeout=300)
    try: tls.close()
    except: pass
    try: client_socket.close()
    except: pass


def handle_http_request(client_socket, target_host, target_port, request_bytes):
    tls = create_https_tunnel(target_host, target_port)
    tls.settimeout(30)
    tls.sendall(request_bytes)
    response = b''
    try:
        while True:
            readable, _, _ = select.select([tls], [], [tls], 10)
            if readable:
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
                        tls.settimeout(5)
                        while True:
                            try:
                                data = tls.recv(65536)
                                if not data:
                                    break
                                response += data
                            except socket.timeout:
                                break
                        tls.settimeout(30)
                    break
    except Exception:
        pass
    client_socket.sendall(response)
    try: tls.close()
    except: pass
    try: client_socket.close()
    except: pass


def handle_client(client_socket):
    try:
        client_socket.settimeout(60)
        request_bytes = b''
        try:
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request_bytes += chunk
                if b'\r\n\r\n' in request_bytes:
                    break
                if len(request_bytes) > 8192:
                    break
        except socket.timeout:
            pass

        if not request_bytes:
            client_socket.close()
            return

        request_str = request_bytes.decode('utf-8', errors='ignore')
        lines = request_str.split('\r\n')
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
            handle_connect(client_socket, target_host, target_port)
        else:
            handle_http_request(client_socket, target_host, target_port, request_bytes)

    except Exception:
        try:
            client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
        except Exception:
            pass
        try:
            client_socket.close()
        except Exception:
            pass


def main():
    global LISTEN_PORT, SESSION, USERNAME, PASSWORD

    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            LISTEN_PORT = int(sys.argv[i + 1])
        if arg == '--session' and i + 1 < len(sys.argv):
            base = sys.argv[i + 1]
            SESSION = f'{base}-sid-{random.randint(100000, 999999999)}'
            USERNAME = SESSION

    print(f"HTTPS wrapper listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    print(f"Session: {SESSION}", flush=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

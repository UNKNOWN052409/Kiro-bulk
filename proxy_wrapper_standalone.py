#!/usr/bin/env python3
"""
High-performance Local HTTP-to-SOCKS5 proxy wrapper with connection pooling.
Listens on 127.0.0.1:8899 and forwards all traffic through ProxyRise SOCKS5 residential proxy.
Uses a CONSISTENT session ID so all connections use the same residential IP.
Implements connection pooling to reuse SOCKS5 connections for the same target host.
"""

import socket, threading, socks, random, sys, time
from collections import defaultdict
from queue import Queue, Empty

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
LISTEN_PORT = 8899

# FIXED session ID for this run - ensures all connections use the same IP
SESSION_ID = 'res-us'

# Connection pool: maps (host, port) -> list of (sock, last_used_time)
_pool_lock = threading.Lock()
_pool = defaultdict(list)
POOL_TIMEOUT = 60  # seconds before a pooled connection is considered stale
MAX_POOL_SIZE = 10  # max connections per host


def create_socks5_connection(host, port, max_retries=3):
    """Create a new SOCKS5 connection with retry logic."""
    for attempt in range(max_retries):
        try:
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, 'gw.proxyrise.com', 443, 
                       username=SESSION_ID, password=PROXYRISE_API_KEY)
            s.settimeout(90)  # Very long timeout for residential proxy
            s.connect((host, port))
            return s
        except Exception as e:
            print(f"  SOCKS5 connect attempt {attempt+1} failed: {e}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))  # Backoff
            else:
                raise e


def get_pooled_connection(host, port):
    """Get a connection from the pool or create a new one."""
    now = time.time()
    key = (host, port)
    
    with _pool_lock:
        # Try to get an existing connection
        while _pool[key]:
            sock, last_used = _pool[key].pop(0)
            if now - last_used < POOL_TIMEOUT:
                # Just use it - don't try to probe (probe might consume data)
                sock.settimeout(90)
                return sock
        
        # Create a new connection with retry
        return create_socks5_connection(host, port)


def return_to_pool(sock, host, port):
    """Return a connection to the pool for reuse."""
    key = (host, port)
    with _pool_lock:
        if len(_pool[key]) < MAX_POOL_SIZE:
            _pool[key].append((sock, time.time()))
        else:
            try:
                sock.close()
            except:
                pass


def handle_https(client_socket, target_host, target_port):
    """Handle HTTPS CONNECT tunneling with connection pooling."""
    s = get_pooled_connection(target_host, target_port)
    client_socket.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
    
    def forward(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except:
            pass
    
    t1 = threading.Thread(target=forward, args=(client_socket, s))
    t2 = threading.Thread(target=forward, args=(s, client_socket))
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()
    t1.join(timeout=300)
    t2.join(timeout=300)
    
    # Try to return to pool
    try:
        return_to_pool(s, target_host, target_port)
    except:
        try:
            s.close()
        except:
            pass
    try:
        client_socket.close()
    except:
        pass


def handle_http(client_socket, target_host, target_port, request):
    """Handle HTTP requests with connection pooling."""
    s = get_pooled_connection(target_host, target_port)
    s.sendall(request.encode())
    
    response = b''
    try:
        while True:
            data = s.recv(65536)
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
                    # Chunked encoding - keep reading until we get 0\r\n\r\n
                    while b'0\r\n\r\n' not in response[-200:]:
                        data = s.recv(65536)
                        if not data:
                            break
                        response += data
                elif content_length is not None:
                    body_start = header_end + 4
                    while len(response[body_start:]) < content_length:
                        data = s.recv(min(65536, content_length - len(response[body_start:])))
                        if not data:
                            break
                        response += data
                else:
                    # No content-length, keep reading until timeout
                    s.settimeout(3)
                    while True:
                        try:
                            data = s.recv(65536)
                            if not data:
                                break
                            response += data
                        except socket.timeout:
                            break
                    s.settimeout(30)
                break
    except Exception:
        pass
    
    client_socket.sendall(response)
    return_to_pool(s, target_host, target_port)
    client_socket.close()


def handle_client(client_socket):
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
                    # Check if there's a body (Content-Length)
                    header_end = request.find(b'\r\n\r\n')
                    headers = request[:header_end].decode('utf-8', errors='ignore')
                    has_content_length = False
                    for line in headers.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            cl = int(line.split(':')[1].strip())
                            has_content_length = True
                            body_so_far = len(request) - header_end - 4
                            if body_so_far >= cl:
                                break
                    if not has_content_length:
                        # No content-length, request headers are complete
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
    except Exception as e:
        try:
            client_socket.close()
        except:
            pass


def main():
    global LISTEN_PORT, SESSION_ID
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            LISTEN_PORT = int(sys.argv[i + 1])
        if arg == '--session' and i + 1 < len(sys.argv):
            SESSION_ID = sys.argv[i + 1]
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.bind(('127.0.0.1', LISTEN_PORT))
    server.listen(200)
    print(f"Proxy wrapper v2 listening on 127.0.0.1:{LISTEN_PORT} with session {SESSION_ID}", flush=True)
    
    while True:
        try:
            client, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client,), daemon=True)
            t.start()
        except Exception as e:
            print(f"Accept error: {e}", flush=True)

if __name__ == '__main__':
    main()

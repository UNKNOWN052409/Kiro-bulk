#!/usr/bin/env python3
"""
Local SOCKS5 proxy bridge (robust version).
Accepts unauthenticated SOCKS5 connections on localhost and forwards them
to ProxyRise with embedded credentials.
Uses asyncio for better concurrent connection handling.
"""

import socket
import threading
import struct
import socks
import sys
import time
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('socks5_bridge')

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXYRISE_HOST = 'gw.proxyrise.com'
PROXYRISE_PORT = 443
SESSION = 'res-us'

LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 10800


def recv_exact(sock, n):
    """Receive exactly n bytes."""
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def forward_bidirectional(sock1, sock2, timeout=300):
    """Forward data bidirectionally between two sockets."""
    import select
    sockets = [sock1, sock2]
    start_time = time.time()
    
    while True:
        if time.time() - start_time > timeout:
            break
        
        try:
            readable, _, errored = select.select(sockets, [], sockets, 1.0)
        except (ValueError, OSError):
            break
        
        if errored:
            break
        
        if not readable:
            continue
        
        for s in readable:
            other = sock2 if s is sock1 else sock1
            try:
                data = s.recv(65536)
                if not data:
                    return  # Connection closed
                other.sendall(data)
            except (OSError, BrokenPipeError, ConnectionResetError):
                return


def handle_client(client_sock, addr):
    """Handle a single SOCKS5 client connection."""
    try:
        # SOCKS5 handshake
        handshake = recv_exact(client_sock, 2)
        if not handshake or handshake[0] != 0x05:
            client_sock.close()
            return
        
        nmethods = handshake[1]
        methods = recv_exact(client_sock, nmethods)
        
        client_sock.sendall(b'\x05\x00')  # SOCKS5, no auth required
        
        # Read connect request
        request = recv_exact(client_sock, 4)
        if not request or request[0] != 0x05:
            client_sock.close()
            return
        
        cmd = request[1]
        atyp = request[3]
        
        if cmd != 0x01:  # Only support CONNECT
            client_sock.sendall(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
            client_sock.close()
            return
        
        # Parse address
        if atyp == 0x01:  # IPv4
            addr_bytes = recv_exact(client_sock, 4)
            target_host = socket.inet_ntoa(addr_bytes)
        elif atyp == 0x03:  # Domain
            domain_len_byte = recv_exact(client_sock, 1)
            if not domain_len_byte:
                client_sock.close()
                return
            domain_len = ord(domain_len_byte)
            domain = recv_exact(client_sock, domain_len)
            if not domain:
                client_sock.close()
                return
            target_host = domain.decode('utf-8')
        elif atyp == 0x04:  # IPv6
            addr_bytes = recv_exact(client_sock, 16)
            target_host = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            client_sock.close()
            return
        
        # Read port
        port_bytes = recv_exact(client_sock, 2)
        if not port_bytes:
            client_sock.close()
            return
        target_port = struct.unpack('!H', port_bytes)[0]
        
        # Connect to target through ProxyRise SOCKS5
        remote_sock = socks.socksocket()
        remote_sock.settimeout(60)
        remote_sock.set_proxy(socks.SOCKS5, PROXYRISE_HOST, PROXYRISE_PORT,
                             username=SESSION, password=PROXYRISE_API_KEY)
        
        try:
            remote_sock.connect((target_host, target_port))
            
            # Send success response
            if atyp == 0x01:
                client_sock.sendall(b'\x05\x00\x00\x01' + b'\x00\x00\x00\x00' + b'\x00\x00')
            elif atyp == 0x03:
                domain_bytes = target_host.encode('utf-8')
                client_sock.sendall(b'\x05\x00\x00\x03' + bytes([len(domain_bytes)]) + domain_bytes + b'\x00\x00')
            elif atyp == 0x04:
                client_sock.sendall(b'\x05\x00\x00\x04' + b'\x00' * 16 + b'\x00\x00')
            
            # Relay data bidirectionally
            forward_bidirectional(client_sock, remote_sock)
            
        except Exception:
            try:
                client_sock.sendall(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
            except:
                pass
        
        client_sock.close()
        remote_sock.close()
        
    except Exception:
        try:
            client_sock.close()
        except:
            pass


def main():
    global LISTEN_PORT, SESSION
    
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            LISTEN_PORT = int(sys.argv[i + 1])
        if arg == '--session' and i + 1 < len(sys.argv):
            SESSION = sys.argv[i + 1]
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(None)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(512)
    print(f"SOCKS5 bridge listening on {LISTEN_HOST}:{LISTEN_PORT} -> ProxyRise (session={SESSION})", flush=True)
    
    while True:
        try:
            client, addr = server.accept()
            client.settimeout(60)
            t = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
            t.start()
        except Exception:
            pass


if __name__ == '__main__':
    main()

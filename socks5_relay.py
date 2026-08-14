#!/usr/bin/env python3
"""
Local SOCKS5 relay that accepts connections without authentication
and forwards them to ProxyRise gateway (gw.proxyrise.com:443) with API key auth.

This allows Chrome to use the proxy without needing to support SOCKS5 auth.
"""

import socket
import threading
import struct
import sys

REMOTE_HOST = 'gw.proxyrise.com'
REMOTE_PORT = 443
API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
LOCAL_PORT = 10800

def handle_client(client_sock, addr):
    """Handle a single client connection."""
    try:
        # SOCKS5 greeting: read method selection
        # Client sends: VER=0x05, NMETHODS, METHODS...
        greeting = client_sock.recv(2)
        if len(greeting) < 2:
            return
        
        nmethods = greeting[1]
        methods = client_sock.recv(nmethods)
        
        # Respond: VER=0x05, METHOD=0x00 (no auth)
        client_sock.sendall(b'\x05\x00')
        
        # Read the CONNECT request
        # VER=0x05, CMD=0x01, RSV=0x00, ATYP, DST...
        header = client_sock.recv(4)
        if len(header) < 4:
            return
        
        atyp = header[3]
        
        if atyp == 0x01:  # IPv4
            dst = client_sock.recv(4)
            if len(dst) < 4:
                return
            remote_addr = socket.inet_ntoa(dst)
        elif atyp == 0x03:  # Domain name
            name_len = client_sock.recv(1)[0]
            name = client_sock.recv(name_len)
            remote_addr = name.decode('ascii')
        elif atyp == 0x04:  # IPv6
            dst = client_sock.recv(16)
            remote_addr = socket.inet_ntop(socket.AF_INET6, dst)
        else:
            return
        
        # Read port
        port_data = client_sock.recv(2)
        if len(port_data) < 2:
            return
        remote_port = struct.unpack('!H', port_data)[0]
        
        # Connect to the remote server (ProxyRise gateway)
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(30)
        
        # For ProxyRise, we connect to the gateway and send the API key
        # during the SOCKS5 authentication phase
        remote_sock.connect((REMOTE_HOST, REMOTE_PORT))
        
        # SOCKS5 authentication with ProxyRise
        # Send: VER=0x05, NMETHODS=0x02, METHOD=0x00 (no auth), METHOD=0x02 (username/password)
        remote_sock.sendall(b'\x05\x02\x00\x02')
        auth_resp = remote_sock.recv(2)
        
        if len(auth_resp) == 2 and auth_resp[1] == 0x02:
            # Server chose username/password auth
            # Send username/password
            username = b'api-US'
            password = API_KEY.encode('ascii')
            auth_data = b'\x01' + bytes([len(username)]) + username + bytes([len(password)]) + password
            remote_sock.sendall(auth_data)
            
            auth_result = remote_sock.recv(2)
            if len(auth_result) == 2 and auth_result[1] != 0x00:
                print(f"[!] Auth failed with ProxyRise: {auth_result}")
                client_sock.sendall(b'\x05\x01')  # General failure
                remote_sock.close()
                return
        
        # Forward the CONNECT request to the remote server
        connect_request = b'\x05\x01\x00' + bytes([atyp])
        if atyp == 0x01:
            connect_request += dst
        elif atyp == 0x03:
            connect_request += bytes([name_len]) + name
        elif atyp == 0x04:
            connect_request += dst
        connect_request += port_data
        
        remote_sock.sendall(connect_request)
        
        # Read the response from remote
        resp_header = remote_sock.recv(4)
        if len(resp_header) < 4:
            client_sock.sendall(b'\x05\x01')  # General failure
            remote_sock.close()
            return
        
        resp_atyp = resp_header[3]
        if resp_atyp == 0x01:
            remote_sock.recv(6)  # IPv4 + port
        elif resp_atyp == 0x03:
            name_len = remote_sock.recv(1)[0]
            remote_sock.recv(name_len + 2)
        elif resp_atyp == 0x04:
            remote_sock.recv(18)  # IPv6 + port
        
        resp_status = resp_header[1]
        if resp_status != 0x00:
            client_sock.sendall(b'\x05' + bytes([resp_status]) + b'\x00')
            remote_sock.close()
            return
        
        # Send success response to client
        bind_addr = socket.gethostbyname('127.0.0.1')
        bind_port = 0
        client_sock.sendall(b'\x05\x00\x00\x01' + socket.inet_aton(bind_addr) + struct.pack('!H', bind_port))
        
        # Now relay data between client and remote
        def relay(src, dst):
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
                    dst.close()
                except:
                    pass
                try:
                    src.close()
                except:
                    pass
        
        t1 = threading.Thread(target=relay, args=(client_sock, remote_sock))
        t2 = threading.Thread(target=relay, args=(remote_sock, client_sock))
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
    except Exception as e:
        pass
    finally:
        try:
            client_sock.close()
        except:
            pass

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', LOCAL_PORT))
    server.listen(128)
    print(f"[+] SOCKS5 relay listening on 127.0.0.1:{LOCAL_PORT}")
    print(f"[+] Forwarding to {REMOTE_HOST}:{REMOTE_PORT} with API key auth")
    
    while True:
        client_sock, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client_sock, addr))
        t.daemon = True
        t.start()

if __name__ == '__main__':
    main()

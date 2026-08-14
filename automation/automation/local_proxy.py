#!/usr/bin/env python3
"""
Local proxy forwarder - adds auth to ProxyRise proxy for Chrome/Opera.
Chrome can't handle proxy auth in URL, so this local proxy adds it.
"""
import socket
import threading
import select
import base64
import sys

class ProxyHandler:
    def __init__(self, remote_host, remote_port, username, password):
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.auth_header = base64.b64encode(f"{username}:{password}".encode()).decode()

    def handle_client(self, client_socket):
        try:
            # Read the initial request
            request = client_socket.recv(8192)
            if not request:
                client_socket.close()
                return

            # Check if it's a CONNECT request (HTTPS)
            first_line = request.split(b'\n')[0].decode('utf-8', errors='ignore')
            is_connect = first_line.startswith('CONNECT')

            if is_connect:
                # For CONNECT, we need to:
                # 1. Connect to remote proxy
                # 2. Send CONNECT with auth
                # 3. Send 200 OK to client
                # 4. Forward data both ways
                self.handle_connect(client_socket, request)
            else:
                # For regular HTTP, add auth header and forward
                self.handle_http(client_socket, request)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            client_socket.close()

    def handle_connect(self, client_socket, request):
        try:
            # Parse the CONNECT request
            first_line = request.split(b'\n')[0].decode('utf-8', errors='ignore')
            target = first_line.split(' ')[1]
            host, port = target.split(':')
            port = int(port)

            # Connect to remote proxy
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.connect((self.remote_host, self.remote_port))

            # Send CONNECT with auth to remote proxy
            connect_req = f"CONNECT {host}:{port} HTTP/1.1\r\n"
            connect_req += f"Host: {host}:{port}\r\n"
            connect_req += f"Proxy-Authorization: Basic {self.auth_header}\r\n"
            connect_req += "\r\n"
            remote_socket.send(connect_req.encode())

            # Read response from remote proxy
            response = remote_socket.recv(8192)
            if b'200' in response.split(b'\n')[0]:
                # Send 200 OK to client
                client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")

                # Forward data both ways
                self.forward_data(client_socket, remote_socket)
            else:
                client_socket.send(response)
                remote_socket.close()

        except Exception as e:
            print(f"Connect error: {e}")
            try:
                client_socket.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except:
                pass

    def handle_http(self, client_socket, request):
        try:
            # Add Proxy-Authorization header
            auth_line = f"Proxy-Authorization: Basic {self.auth_header}\r\n"

            # Insert auth header after the first line
            lines = request.split(b'\n')
            first_line = lines[0]
            rest = b'\n'.join(lines[1:])

            modified_request = first_line + b'\n' + auth_line.encode() + rest

            # Connect to remote proxy
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.connect((self.remote_host, self.remote_port))

            # Forward the modified request
            remote_socket.send(modified_request)

            # Forward response back
            self.forward_data(client_socket, remote_socket)

        except Exception as e:
            print(f"HTTP error: {e}")

    def forward_data(self, client, remote):
        """Forward data between client and remote."""
        sockets = [client, remote]
        timeout = 60

        while True:
            readable, _, errored = select.select(sockets, [], sockets, timeout)
            if errored:
                break
            if not readable:
                break

            for sock in readable:
                try:
                    data = sock.recv(8192)
                    if not data:
                        return
                    if sock is client:
                        remote.send(data)
                    else:
                        client.send(data)
                except:
                    return


def start_proxy(local_port, remote_host, remote_port, username, password):
    """Start the local proxy server."""
    handler = ProxyHandler(remote_host, remote_port, username, password)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', local_port))
    server.listen(5)

    print(f"Local proxy running on 127.0.0.1:{local_port}")
    print(f"Forwarding to {remote_host}:{remote_port} with auth")

    while True:
        client_socket, addr = server.accept()
        thread = threading.Thread(target=handler.handle_client, args=(client_socket,))
        thread.daemon = True
        thread.start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Local proxy forwarder with auth")
    parser.add_argument("--local-port", type=int, default=8888, help="Local port (default: 8888)")
    parser.add_argument("--remote-host", default="172.65.145.196", help="Remote proxy host")
    parser.add_argument("--remote-port", type=int, default=3389, help="Remote proxy port")
    parser.add_argument("--username", default="res-us", help="Proxy username")
    parser.add_argument("--password", default="pgw-d890748b9e9c734c66a3c1a327fd1db84724cad6cbbe440d", help="Proxy password")

    args = parser.parse_args()
    start_proxy(args.local_port, args.remote_host, args.remote_port, args.username, args.password)
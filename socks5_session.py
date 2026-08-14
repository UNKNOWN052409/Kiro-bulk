"""
Persistent SOCKS5 Session Manager
Creates ONE SOCKS5 connection to ProxyRise and reuses it for all HTTP requests.
This ensures all requests go through the SAME residential IP.
"""

import socket
import socks
import ssl
import json
import threading
from urllib.parse import urlparse


class Socks5Session:
    """A persistent SOCKS5 session that maintains one connection to ProxyRise
    and tunnels all HTTPS requests through it."""
    
    def __init__(self, host='gw.proxyrise.com', port=443, username='res-us', password=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._lock = threading.Lock()
        self._connections = {}  # (target_host, target_port) -> socket
        self._ip = None
    
    def get_ip(self):
        """Check what IP this session is using."""
        resp = self.request('GET', 'https://api.ipquery.io/?format=json')
        if resp:
            data = json.loads(resp.text)
            self._ip = data.get('ip', 'unknown')
            return self._ip
        return None
    
    def request(self, method, url, headers=None, body=None, timeout=30):
        """Make an HTTP request through the persistent SOCKS5 connection."""
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or 443
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        
        conn_key = (host, port)
        
        with self._lock:
            if conn_key not in self._connections:
                # Create new SOCKS5 connection with timeout
                s = socks.socksocket()
                s.settimeout(10)  # Connection timeout
                s.set_proxy(socks.SOCKS5, self.host, self.port, 
                           username=self.username, password=self.password)
                print(f"    Connecting to {host}:{port} via SOCKS5...")
                s.connect((host, port))
                print(f"    SOCKS5 connected! Now doing SSL handshake...")
                
                # Wrap in SSL - need to handle PySocks socket properly
                try:
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    # PySocks socksocket might not work directly with wrap_socket
                    # Try wrapping the underlying socket
                    s = ctx.wrap_socket(s, server_hostname=host)
                    print(f"    SSL handshake done!")
                except Exception as e:
                    print(f"    SSL wrap failed: {e}")
                    # Try alternative: use ssl.wrap_socket directly
                    s = ssl.wrap_socket(s, server_hostname=host)
                    print(f"    SSL wrap (alt) done!")
                
                self._connections[conn_key] = s
            
            sock = self._connections[conn_key]
        
        # Build HTTP request
        if headers is None:
            headers = {}
        
        request_lines = [f'{method} {path} HTTP/1.1']
        if 'host' not in {k.lower() for k in headers}:
            request_lines.append(f'Host: {host}')
        
        for k, v in headers.items():
            request_lines.append(f'{k}: {v}')
        
        if body:
            if isinstance(body, str):
                body = body.encode('utf-8')
            request_lines.append(f'Content-Length: {len(body)}')
        
        request_lines.append('Connection: keep-alive')
        request_lines.append('')
        request_lines.append('')
        
        request_str = '\r\n'.join(request_lines)
        
        try:
            sock.settimeout(timeout)
            sock.sendall(request_str.encode('utf-8'))
            if body:
                sock.sendall(body)
            
            # Read response - read all data until connection closes or timeout
            response_data = b''
            content_length = None
            is_chunked = False
            headers_parsed = False
            
            while True:
                try:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    response_data += chunk
                    
                    # Parse headers once we have them
                    if not headers_parsed and b'\r\n\r\n' in response_data:
                        header_end = response_data.index(b'\r\n\r\n')
                        headers_raw = response_data[:header_end].decode('utf-8', errors='ignore')
                        headers_parsed = True
                        
                        for line in headers_raw.split('\r\n'):
                            lower_line = line.lower()
                            if lower_line.startswith('content-length:'):
                                content_length = int(line.split(':')[1].strip())
                            elif lower_line.startswith('transfer-encoding:') and 'chunked' in lower_line:
                                is_chunked = True
                    
                    # Check if we have the full response
                    if headers_parsed:
                        header_end = response_data.index(b'\r\n\r\n')
                        body_start = header_end + 4
                        body_so_far = response_data[body_start:]
                        
                        if is_chunked:
                            # For chunked, look for the terminal chunk
                            if b'0\r\n\r\n' in body_so_far:
                                break
                        elif content_length is not None:
                            if len(body_so_far) >= content_length:
                                break
                        else:
                            # No content-length and not chunked - wait for timeout
                            # This handles keep-alive connections
                            pass
                except socket.timeout:
                    break
                except Exception as e:
                    print(f"    [READ ERR] {e}")
                    break
            
            return self._parse_response(response_data)
        except Exception as e:
            # Connection might be dead, remove it
            with self._lock:
                self._connections.pop(conn_key, None)
            print(f"    [SOCKS5 ERR] {e}")
            return None
    
    def _parse_response(self, data):
        """Parse HTTP response bytes into a simple object."""
        if not data:
            return None
        
        # Split headers and body
        header_end = data.find(b'\r\n\r\n')
        if header_end == -1:
            return None
        
        headers_raw = data[:header_end].decode('utf-8', errors='ignore')
        body = data[header_end + 4:]
        
        # Parse status code
        lines = headers_raw.split('\r\n')
        status_line = lines[0]
        status_code = int(status_line.split(' ')[1])
        
        # Parse headers
        headers = {}
        for line in lines[1:]:
            if ':' in line:
                k, v = line.split(':', 1)
                headers[k.strip().lower()] = v.strip()
        
        # Handle chunked transfer encoding
        if headers.get('transfer-encoding', '') == 'chunked':
            body = self._decode_chunked(body)
        
        return Socks5Response(status_code, headers, body)
    
    def _decode_chunked(self, data):
        """Decode chunked transfer encoding."""
        result = b''
        pos = 0
        while pos < len(data):
            # Find chunk size
            line_end = data.find(b'\r\n', pos)
            if line_end == -1:
                break
            chunk_size_str = data[pos:line_end].decode('utf-8', errors='ignore').strip()
            try:
                chunk_size = int(chunk_size_str, 16)
            except ValueError:
                break
            if chunk_size == 0:
                break
            pos = line_end + 2
            chunk = data[pos:pos + chunk_size]
            result += chunk
            pos = pos + chunk_size + 2  # +2 for \r\n after chunk
        
        return result
    
    def close(self):
        with self._lock:
            for s in self._connections.values():
                try:
                    s.close()
                except:
                    pass
            self._connections.clear()


class Socks5Response:
    def __init__(self, status_code, headers, content):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.text = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else str(content)
    
    def json(self):
        return json.loads(self.text)

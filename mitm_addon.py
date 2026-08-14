"""
mitmproxy addon that logs all requests and responses to a JSON file.
"""

import json
import time


class RequestLogger:
    def __init__(self):
        self.captured = []
        self.log_file = '/home/ubuntu/kiro-gen/captured_flow.json'

    def _save(self):
        with open(self.log_file, 'w') as f:
            json.dump(self.captured, f, indent=2)

    def request(self, flow):
        entry = {
            'type': 'request',
            'timestamp': time.time(),
            'method': flow.request.method,
            'url': flow.request.pretty_url,
            'host': flow.request.pretty_host,
            'path': flow.request.path,
            'headers': dict(flow.request.headers),
            'body': flow.request.get_text() if flow.request.content else None,
            'content_length': len(flow.request.content) if flow.request.content else 0,
        }
        self.captured.append(entry)
        self._save()
        # Print summary to console
        body_preview = ''
        if entry['body'] and len(entry['body']) < 200:
            body_preview = f" | body: {entry['body'][:200]}"
        print(f"[REQ] {entry['method']} {entry['url'][:100]}{body_preview}")

    def response(self, flow):
        entry = {
            'type': 'response',
            'timestamp': time.time(),
            'method': flow.request.method,
            'url': flow.request.pretty_url,
            'status_code': flow.response.status_code if flow.response else 0,
            'headers': dict(flow.response.headers) if flow.response else {},
            'body': flow.response.get_text() if flow.response and flow.response.content else None,
            'content_length': len(flow.response.content) if flow.response and flow.response.content else 0,
        }
        self.captured.append(entry)
        self._save()
        # Print summary
        body_preview = ''
        if entry['body'] and len(entry['body']) < 200:
            body_preview = f" | body: {entry['body'][:200]}"
        print(f"[RESP] {entry['status_code']} {entry['url'][:80]}{body_preview}")


addons = [RequestLogger()]

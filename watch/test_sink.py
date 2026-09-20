#!/usr/bin/env python3
"""Tiny local webhook sink for end-to-end delivery tests: POSTs land in a jsonl file."""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

SINK = sys.argv[2] if len(sys.argv) > 2 else "/tmp/hmwatch-sink.jsonl"


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace")
        with open(SINK, "a") as fh:
            fh.write(json.dumps({"path": self.path, "body": body}) + "\n")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    print(f"sink listening on 127.0.0.1:{port} -> {SINK}", flush=True)
    HTTPServer(("127.0.0.1", port), H).serve_forever()

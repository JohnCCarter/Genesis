import http.server
import socketserver
import os

PORT = int(os.environ.get("TEST_STUB_PORT", "8000"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Minimal Socket.IO polling handshake stub
        if self.path.startswith("/ws/socket.io/") and "transport=polling" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        # Generic OK for healthz
        if self.path in ("/health", "/healthz", "/ready"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"healthy")
            return
        # Default: 404
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"not found")


def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Test stub server listening on 127.0.0.1:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

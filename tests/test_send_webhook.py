import asyncio
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
#import ntfy_to_sip
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
    import ntfy_to_sip


def run_test_server(port):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.server.received_path = self.path
            length = int(self.headers.get('Content-Length', 0))
            self.server.received_body = self.rfile.read(length)
            self.send_response(200)
            self.end_headers()
    httpd = HTTPServer(('0.0.0.0', port), Handler)
    httpd.received_path = None
    httpd.received_body = None
    threading.Thread(target=httpd.handle_request, daemon=True).start()
    return httpd

def get_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def test_send_webhook():
    port = get_free_port()
    httpd = run_test_server(port)
    os.environ['WEBHOOK_HOST'] = '127.0.0.1'
    os.environ['WEBHOOK_PORT'] = str(port)
    os.environ['WEBHOOK_PATH'] = '/hook'
    importlib.reload(ntfy_to_sip)
    msg = {'title': 'test', 'message': 'hello', 'priority': 4}
    asyncio.run(ntfy_to_sip.send_webhook(msg))
    assert httpd.received_path == '/hook'
    body = json.loads(httpd.received_body.decode())
    assert body == msg

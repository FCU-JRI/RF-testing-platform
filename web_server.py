from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json
import urllib.parse
import sys
import os

# Try importing serial to list ports
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

class SSEHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    
    def log_message(self, format, *args):
        # Suppress logging to keep CLI/GUI terminal clean
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        query = urllib.parse.parse_qs(url.query)

        if path == '/api/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            client_queue = threading.Event()
            self.server.add_client(self, client_queue)
            
            try:
                # Keep connection alive with heartbeat
                while not client_queue.wait(timeout=5.0):
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                self.server.remove_client(self)
                
        elif path == '/api/status':
            status = self.server.get_status_callback()
            self.send_json_response(status)
            
        else:
            self.serve_static_file(path)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        
        if path == '/api/control':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                params = json.loads(post_data) if post_data else {}
                action = params.get('action')
                
                result = self.server.execute_action_callback(action, params)
                self.send_json_response(result)
            except Exception as e:
                self.send_json_response({"status": "error", "message": str(e)}, status_code=400)
        else:
            self.send_response(404)
            self.end_headers()

    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def serve_static_file(self, path):
        if path == '/' or path == '':
            path = '/index.html'
            
        safe_path = path.lstrip('/')
        if '..' in safe_path:
            self.send_response(403)
            self.end_headers()
            return

        file_path = os.path.join(self.server.web_root, safe_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            
            # Determine content type
            if file_path.endswith('.html'):
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            elif file_path.endswith('.css'):
                self.send_header('Content-Type', 'text/css')
            elif file_path.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript')
            elif file_path.endswith('.png'):
                self.send_header('Content-Type', 'image/png')
            elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                self.send_header('Content-Type', 'image/jpeg')
            else:
                self.send_header('Content-Type', 'application/octet-stream')
                
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

class WebServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, web_root, get_status_callback, execute_action_callback):
        super().__init__(server_address, RequestHandlerClass)
        self.web_root = web_root
        self.get_status_callback = get_status_callback
        self.execute_action_callback = execute_action_callback
        self.clients = {}
        self.clients_lock = threading.Lock()

    def add_client(self, handler, event):
        with self.clients_lock:
            self.clients[handler] = event

    def remove_client(self, handler):
        with self.clients_lock:
            if handler in self.clients:
                del self.clients[handler]

    def broadcast(self, data_dict):
        msg = f"data: {json.dumps(data_dict)}\n\n".encode('utf-8')
        with self.clients_lock:
            dead_clients = []
            for handler in self.clients:
                try:
                    handler.wfile.write(msg)
                    handler.wfile.flush()
                except Exception:
                    dead_clients.append(handler)
            
            for handler in dead_clients:
                if handler in self.clients:
                    self.clients[handler].set()
                    del self.clients[handler]

def start_web_server(port, web_root, get_status_callback, execute_action_callback):
    bound = False
    attempts = 0
    server = None
    while not bound and attempts < 10:
        try:
            server = WebServer(('0.0.0.0', port), SSEHandler, web_root, get_status_callback, execute_action_callback)
            bound = True
        except OSError:
            port += 1
            attempts += 1
    if not bound:
        print(f"[Web Server] Failed to start Web Server after 10 attempts.")
        return None
    
    server.web_port = port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[Web Server] Serving HTTP and API on http://127.0.0.1:{port} ...")
    return server

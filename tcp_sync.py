import socket
import threading
import time

class TCPSyncManager:
    def __init__(self, port=50077, on_command_received=None, log_func=None):
        self.port = port
        self.on_command_received = on_command_received
        self.log_func = log_func or print
        self.server_socket = None
        self.peer_socket = None
        self.peer_ip = None
        self.running = True
        self.lock = threading.Lock()
        
        # Start server thread
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

    def log(self, msg):
        if self.log_func:
            self.log_func(msg)

    def _server_loop(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        bound = False
        attempts = 0
        original_port = self.port
        while not bound and attempts < 10:
            try:
                self.server_socket.bind(('0.0.0.0', self.port))
                self.server_socket.listen(1)
                self.log(f"Listening on port {self.port} for parameter sync...")
                bound = True
            except OSError:
                attempts += 1
                self.port += 1
            except Exception as e:
                self.log(f"Failed to bind TCP server: {e}")
                return
        if not bound:
            self.log(f"Failed to bind TCP server after 10 attempts starting from port {original_port}")
            return

        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    conn, addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                
                self.log(f"Received sync connection from {addr[0]}")
                with self.lock:
                    if self.peer_socket:
                        try:
                            self.peer_socket.close()
                        except:
                            pass
                    self.peer_socket = conn
                    self.peer_ip = addr[0]
                
                threading.Thread(target=self._receive_loop, args=(conn, addr[0]), daemon=True).start()
            except Exception as e:
                if self.running:
                    self.log(f"Server loop exception: {e}")
                break

    def connect_to_peer(self, ip, port=None):
        if ":" in ip:
            try:
                ip, port_str = ip.split(":")
                port = int(port_str)
            except ValueError:
                pass
        if port is None:
            port = self.port
        threading.Thread(target=self._connect, args=(ip, port), daemon=True).start()

    def _connect(self, ip, port):
        self.log(f"Connecting to peer {ip}:{port}...")
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(5.0)
            conn.connect((ip, port))
            self.log(f"Connected to peer {ip} successfully!")
            with self.lock:
                if self.peer_socket:
                    try:
                        self.peer_socket.close()
                    except:
                        pass
                self.peer_socket = conn
                self.peer_ip = ip
            
            threading.Thread(target=self._receive_loop, args=(conn, ip), daemon=True).start()
            return True
        except Exception as e:
            self.log(f"Failed to connect to peer {ip}: {e}")
            return False

    def _receive_loop(self, conn, ip):
        conn.settimeout(None)
        buffer = ""
        while self.running:
            try:
                data = conn.recv(1024)
                if not data:
                    self.log(f"Sync connection closed by peer {ip}")
                    break
                buffer += data.decode('utf-8', errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        # Call on_command_received callback
                        if self.on_command_received:
                            try:
                                self.on_command_received(line)
                            except Exception as ex:
                                self.log(f"Error executing command: {ex}")
            except Exception as e:
                self.log(f"Sync connection error with {ip}: {e}")
                break
        
        with self.lock:
            if self.peer_socket == conn:
                self.peer_socket = None
                self.peer_ip = None

    def send_command(self, cmd):
        cmd_str = cmd.strip() + '\n'
        with self.lock:
            conn = self.peer_socket
        if conn:
            try:
                conn.sendall(cmd_str.encode('utf-8'))
                return True
            except Exception as e:
                self.log(f"Failed to send sync command to peer: {e}")
                self.disconnect_peer()
                return False
        return False

    def disconnect_peer(self):
        with self.lock:
            if self.peer_socket:
                try:
                    self.peer_socket.close()
                except:
                    pass
                self.peer_socket = None
                self.peer_ip = None
        self.log("Disconnected from peer.")

    def is_connected(self):
        with self.lock:
            return self.peer_socket is not None

    def get_peer_info(self):
        with self.lock:
            if self.peer_socket:
                return self.peer_ip
            return None

    def close(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        self.disconnect_peer()

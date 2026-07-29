#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PeerSyncSocket — Machine-to-Machine IP Parameter Synchronization Module.
Provides lightweight TCP socket communication to synchronize RF parameters across
multiple IP-connected test stations and update dual-monitor UI controls in lockstep.
"""

import socket
import threading
import json
import time
from typing import Optional, Callable

DEFAULT_SYNC_PORT = 50077

class PeerSyncManager:
    def __init__(self, port: int = DEFAULT_SYNC_PORT, on_param_received: Optional[Callable[[str], None]] = None):
        self.port = port
        self.on_param_received = on_param_received
        self.running = False
        self.peer_ip: Optional[str] = None

        self._server_sock: Optional[socket.socket] = None
        self._peer_sock: Optional[socket.socket] = None
        self.lock = threading.Lock()

        self.start_server()

    def start_server(self):
        self.running = True
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(('0.0.0.0', self.port))
            self._server_sock.listen(2)
            threading.Thread(target=self._listen_loop, daemon=True).start()
        except Exception as e:
            print(f"[PeerSync] Server start failed on port {self.port}: {e}")

    def _listen_loop(self):
        while self.running and self._server_sock:
            try:
                conn, addr = self._server_sock.accept()
                with self.lock:
                    self._peer_sock = conn
                    self.peer_ip = addr[0]
                threading.Thread(target=self._recv_loop, args=(conn,), daemon=True).start()
            except Exception:
                break

    def connect_peer(self, ip: str, port: int = DEFAULT_SYNC_PORT) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            with self.lock:
                self._peer_sock = sock
                self.peer_ip = ip
            threading.Thread(target=self._recv_loop, args=(sock,), daemon=True).start()
            return True
        except Exception as e:
            print(f"[PeerSync] Connect to {ip}:{port} failed: {e}")
            return False

    def send_param_cmd(self, cmd_str: str):
        with self.lock:
            if not self._peer_sock:
                return
            try:
                payload = json.dumps({"type": "param_sync", "cmd": cmd_str.strip()}) + "\n"
                self._peer_sock.sendall(payload.encode('utf-8'))
            except Exception as e:
                print(f"[PeerSync] Send error: {e}")
                self._peer_sock = None
                self.peer_ip = None

    def _recv_loop(self, conn: socket.socket):
        conn_file = conn.makefile('r', encoding='utf-8', errors='ignore')
        while self.running:
            try:
                line = conn_file.readline()
                if not line:
                    break
                data = json.loads(line.strip())
                if data.get('type') == 'param_sync':
                    cmd = data.get('cmd')
                    if cmd and self.on_param_received:
                        self.on_param_received(cmd)
            except Exception:
                break
        with self.lock:
            if self._peer_sock == conn:
                self._peer_sock = None
                self.peer_ip = None

    def close(self):
        self.running = False
        with self.lock:
            if self._peer_sock:
                try:
                    self._peer_sock.close()
                except Exception:
                    pass
                self._peer_sock = None
            if self._server_sock:
                try:
                    self._server_sock.close()
                except Exception:
                    pass
                self._server_sock = None

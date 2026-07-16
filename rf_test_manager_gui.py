#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import uuid
import csv
import subprocess
import datetime
import threading
import queue
import urllib.request
import urllib.parse
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import shutil
from tcp_sync import TCPSyncManager

class HttpSseSerialBridge:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.is_open = True
        self._q = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._sse_loop, daemon=True)
        self._thread.start()
        
    def _sse_loop(self):
        req = urllib.request.Request(self.base_url + '/api/stream')
        req.add_header('Cache-Control', 'no-cache')
        req.add_header('Accept', 'text/event-stream')
        while not self._stop_event.is_set():
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    for line in response:
                        if self._stop_event.is_set():
                            break
                        line = line.decode('utf-8').strip()
                        if line.startswith('data:'):
                            try:
                                data = json.loads(line[5:])
                                if data.get('type') == 'serial_data':
                                    self._q.put((data['data'] + '\n').encode('utf-8'))
                            except: pass
            except Exception:
                time.sleep(2)
                
    def read(self, size=1):
        return b''
        
    def readline(self):
        try:
            return self._q.get(timeout=0.1)
        except queue.Empty:
            return b''
            
    def write(self, data):
        cmd_str = data.decode('utf-8').strip()
        payload = json.dumps({"action": "send_command", "cmd": cmd_str}).encode('utf-8')
        req = urllib.request.Request(self.base_url + '/api/control', data=payload)
        req.add_header('Content-Type', 'application/json')
        try:
            urllib.request.urlopen(req, timeout=2)
        except: pass
        
    def close(self):
        self.is_open = False
        self._stop_event.set()

tcp_sync_mgr = None
web_srv = None
gui_app = None

def get_web_status():
    return {"status": "gui_mode"}

def execute_web_action(action, params):
    global gui_app
    if not gui_app:
        return {"status": "error", "message": "GUI not ready"}
        
    active_serial = None
    for node in [gui_app.nodeA, gui_app.nodeB]:
        if node.running and node.serial_conn and not isinstance(node.serial_conn, HttpSseSerialBridge):
            active_serial = node.serial_conn
            break
            
    if action == 'send_command':
        cmd = params.get('cmd')
        if cmd and active_serial:
            active_serial.write((cmd.strip() + '\n').encode('utf-8'))
            return {"status": "ok"}
        return {"status": "error", "message": "No active serial"}
        
    elif action == 'apply_settings':
        freq, bw, cr, sf, length = params.get('freq'), params.get('bw'), params.get('cr'), params.get('sf'), params.get('len')
        if active_serial:
            if freq: active_serial.write(f"f {int(float(freq)*1E6)}\n".encode('utf-8')); time.sleep(0.05)
            if bw: active_serial.write(f"b {bw}\n".encode('utf-8')); time.sleep(0.05)
            if cr: active_serial.write(f"c {cr}\n".encode('utf-8')); time.sleep(0.05)
            if sf: active_serial.write(f"v {sf}\n".encode('utf-8')); time.sleep(0.05)
            if length: active_serial.write(f"l {length}\n".encode('utf-8')); time.sleep(0.05)
            return {"status": "ok"}
        return {"status": "error", "message": "No active serial"}
        
    elif action == 'start_test':
        test_type, sf, interval = params.get('type'), params.get('sf', '7'), params.get('interval', '150')
        if active_serial:
            if test_type == 'formal': active_serial.write(f"{sf}\n".encode('utf-8'))
            elif test_type == 'pre': active_serial.write(f"p {sf}\n".encode('utf-8'))
            elif test_type == 'stress': active_serial.write(f"s {sf} {interval}\n".encode('utf-8'))
            elif test_type == 'stop': active_serial.write(b"x\n")
            return {"status": "ok"}
        return {"status": "error", "message": "No active serial"}
        
    return {"status": "error", "message": f"Unknown action: {action}"}

def sync_send_command(cmd):
    global tcp_sync_mgr
    if not tcp_sync_mgr or not tcp_sync_mgr.is_connected():
        return
    cmd = cmd.strip()
    if cmd.isdigit() and 6 <= int(cmd) <= 12:
        tcp_sync_mgr.send_command(f"v {cmd}")
    elif cmd == 'p':
        tcp_sync_mgr.send_command("v 7")
    elif cmd.startswith("p "):
        parts = cmd.split()
        sf = parts[1] if len(parts) > 1 else "7"
        tcp_sync_mgr.send_command(f"v {sf}")
    elif cmd.startswith("s "):
        parts = cmd.split()
        sf = parts[1] if len(parts) > 1 else "7"
        tcp_sync_mgr.send_command(f"v {sf}")
    elif cmd == 'x':
        tcp_sync_mgr.send_command("x")
    elif any(cmd.startswith(prefix) for prefix in ["f ", "b ", "c ", "l ", "u ", "v "]):
        tcp_sync_mgr.send_command(cmd)


class ThreadSafeConsole:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        self.text_widget.after(0, self._write, text)

    def _write(self, text):
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)

class NodePanel(ttk.Frame):
    def __init__(self, parent, node_name):
        super().__init__(parent, padding=10)
        self.node_name = node_name
        self.serial_conn = None
        self.running = False
        self.current_uuid = None
        self.csv_file = None
        self.csv_writer = None
        self.session_stats = {}
        self.peer_url = None   # set when connected via HTTP to a remote peer
        
        self.setup_ui()
        
    def setup_ui(self):
        # Connection
        conn_frame = ttk.LabelFrame(self, text=f"Connection - Node {self.node_name}", padding=10)
        conn_frame.pack(fill='x', pady=5)
        
        ttk.Label(conn_frame, text="Port/URL:").pack(side='left')
        self.port_cb = ttk.Combobox(conn_frame, width=32)
        self.port_cb.pack(side='left', padx=5)
        self.btn_conn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.btn_conn.pack(side='left', padx=5)
        ttk.Label(conn_frame, text="(支援 COM3, socket://IP:PORT, http://IP:8080)", foreground="gray").pack(side='left')
        
        # Operation Mode
        mode_frame = ttk.LabelFrame(self, text="Operation Role", padding=10)
        mode_frame.pack(fill='x', pady=5)
        
        self.mode_var = tk.StringVar(value="rx")
        ttk.Radiobutton(mode_frame, text="Receiver (RX) Mode", variable=self.mode_var, value="rx", command=self.on_mode_change).pack(side='left', padx=10)
        ttk.Radiobutton(mode_frame, text="Transmitter (TX) Mode", variable=self.mode_var, value="tx", command=self.on_mode_change).pack(side='left', padx=10)
        
        # TX Controls (initially disabled)
        self.tx_frame = ttk.Frame(mode_frame)
        self.tx_frame.pack(side='left', fill='x', expand=True, padx=20)
        
        ttk.Label(self.tx_frame, text="Int(ms):").grid(row=0, column=0, padx=2)
        self.tx_int = tk.StringVar(value="150")
        ttk.Entry(self.tx_frame, textvariable=self.tx_int, width=5).grid(row=0, column=1, padx=2)
        
        ttk.Button(self.tx_frame, text="Formal", command=lambda: self.send_tx_cmd("formal")).grid(row=0, column=2, padx=2)
        ttk.Button(self.tx_frame, text="Stress", command=lambda: self.send_tx_cmd("stress")).grid(row=0, column=3, padx=2)
        ttk.Button(self.tx_frame, text="Pre-Test", command=lambda: self.send_tx_cmd("pre")).grid(row=0, column=4, padx=2)
        ttk.Button(self.tx_frame, text="Stop", command=lambda: self.send_tx_cmd("stop")).grid(row=0, column=5, padx=2)        
        # Dynamic Settings
        dyn_frame = ttk.LabelFrame(self, text="Dynamic LoRa Settings (Applies Immediately)", padding=10)
        dyn_frame.pack(fill='x', pady=5)
        
        ttk.Label(dyn_frame, text="Freq (MHz):").grid(row=0, column=0)
        self.dyn_f = ttk.Combobox(dyn_frame, values=["433", "915"], width=5)
        self.dyn_f.current(1)
        self.dyn_f.grid(row=0, column=1, padx=2)

        ttk.Label(dyn_frame, text="BW (Hz):").grid(row=0, column=2, padx=(5,0))
        self.dyn_b = ttk.Combobox(dyn_frame, values=["125000", "250000", "500000", "62500", "31250"], width=8)
        self.dyn_b.current(0)
        self.dyn_b.grid(row=0, column=3, padx=2)

        ttk.Label(dyn_frame, text="CR(4/x):").grid(row=0, column=4, padx=(5,0))
        self.dyn_c = ttk.Combobox(dyn_frame, values=["5", "6", "7", "8"], width=3)
        self.dyn_c.current(1)
        self.dyn_c.grid(row=0, column=5, padx=2)

        ttk.Label(dyn_frame, text="SF:").grid(row=0, column=6, padx=(5,0))
        self.dyn_s = ttk.Combobox(dyn_frame, values=["6", "7", "8", "9", "10", "11", "12"], width=3)
        self.dyn_s.current(1)
        self.dyn_s.grid(row=0, column=7, padx=2)
        
        ttk.Button(dyn_frame, text="Apply", command=self.apply_settings).grid(row=0, column=8, padx=10)
        
        # Console
        self.console = scrolledtext.ScrolledText(self, height=15, bg='#1e1e1e', fg='#00ff00', font=('Consolas', 11))
        self.console.pack(fill='both', expand=True, pady=5)
        self.out = ThreadSafeConsole(self.console)
        
        self.update_ui_state()

    def update_ui_state(self):
        mode = self.mode_var.get()
        if mode == 'tx':
            self.tx_frame.pack(side='left', fill='x', expand=True, padx=20)
        else:
            self.tx_frame.pack_forget()

    def on_mode_change(self):
        self.update_ui_state()
        if self.mode_var.get() == "rx":
            self.send_raw("x") # Force MCU into RX mode explicitly
            self.out.write(f"[GUI] Node {self.node_name} switched to Receiver. Commanded MCU to RX mode.\n")
        else:
            self.out.write(f"[GUI] Node {self.node_name} switched to Transmitter. Ready to initiate test.\n")

    def http_sync_send(self, cmd):
        """POST a command to the remote peer's API server."""
        if not self.peer_url:
            return
        try:
            payload = json.dumps({"action": "send_command", "cmd": cmd}).encode('utf-8')
            req = urllib.request.Request(self.peer_url.rstrip('/') + '/api/control', data=payload)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=2)
        except Exception as e:
            self.out.write(f"[SYNC] HTTP send failed: {e}\n")

    def toggle_connection(self):
        if not self.running:
            port = self.port_cb.get().strip()
            if not port or "No devices" in port:
                messagebox.showerror("Error", "Invalid port!")
                return
            try:
                if port.startswith("http://") or port.startswith("https://"):
                    self.serial_conn = HttpSseSerialBridge(port)
                    self.peer_url = port
                else:
                    self.serial_conn = serial.serial_for_url(port, baudrate=115200, timeout=0.1)
                    self.peer_url = None
                self.running = True
                self.btn_conn.config(text="Disconnect")
                self.out.write(f"[INFO] Connected to {port}\n")
                
                if self.mode_var.get() == "rx":
                    self.send_raw("x")
                    
                threading.Thread(target=self.read_loop, daemon=True).start()
            except Exception as e:
                self.out.write(f"[ERROR] {e}\n")
        else:
            self.running = False
            if self.serial_conn:
                self.serial_conn.close()
            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
            self.peer_url = None
            self.btn_conn.config(text="Connect")
            self.out.write("[INFO] Disconnected\n")

    RF_PARAM_PREFIXES = ('f ', 'b ', 'c ', 'v ', 'l ')

    def _is_rf_param_cmd(self, cmd):
        """Return True only for RF parameter commands that should sync to peer."""
        c = cmd.strip()
        return any(c.startswith(p) for p in self.RF_PARAM_PREFIXES)

    def send_raw(self, cmd, from_sync=False):
        global gui_app
        if self.running and self.serial_conn:
            self.serial_conn.write((cmd + '\n').encode())
            if not from_sync:
                if isinstance(self.serial_conn, HttpSseSerialBridge):
                    # HTTP mode: command already forwarded via HttpSseSerialBridge.write()
                    # Additionally push RF params to the other local NodePanel if it's a local COM
                    if gui_app and self._is_rf_param_cmd(cmd):
                        peer = gui_app.nodeB if self.node_name == 'A' else gui_app.nodeA
                        if peer and peer.running and peer.serial_conn and not isinstance(peer.serial_conn, HttpSseSerialBridge):
                            peer.send_raw(cmd, from_sync=True)
                else:
                    # Local COM: forward RF params to remote peer's API if connected via HTTP
                    if gui_app and self._is_rf_param_cmd(cmd):
                        peer = gui_app.nodeB if self.node_name == 'A' else gui_app.nodeA
                        if peer and peer.peer_url:
                            threading.Thread(target=peer.http_sync_send, args=(cmd,), daemon=True).start()
                    # Also TCP sync for legacy Tailscale mode
                    sync_send_command(cmd)

    def apply_settings(self):
        f_val = self.dyn_f.get()
        b_val = self.dyn_b.get()
        c_val = self.dyn_c.get()
        s_val = self.dyn_s.get()
        if f_val:
            self.send_raw(f"f {int(float(f_val)*1E6)}")
            time.sleep(0.05)
            
        if b_val:
            self.send_raw(f"b {b_val}")
            time.sleep(0.05)
            
        if c_val:
            self.send_raw(f"c {c_val}")
            time.sleep(0.05)
            
        if s_val:
            self.send_raw(f"v {s_val}")
            time.sleep(0.05)

    def send_tx_cmd(self, test_type):
        if not self.running or not self.serial_conn:
            messagebox.showwarning("Warning", "Connect first!")
            return
            
        if test_type == "stop":
            self.send_raw("x")
            self.out.write("\n[INFO] Sent STOP command.\n")
            return
            
        test_uuid = str(uuid.uuid4())
        self.out.write(f"\n[INFO] Starting {test_type} test. UUID: {test_uuid}\n")
        self.send_raw(f"u {test_uuid}")
        time.sleep(0.2)
        
        sf = self.dyn_s.get()
        interval = self.tx_int.get()
        
        if test_type == "formal":
            self.send_raw(f"{sf}")
        elif test_type == "stress":
            self.send_raw(f"s {sf} {interval}")
        elif test_type == "pre":
            self.send_raw(f"p {sf}")

    def read_loop(self):
        os.makedirs('logs', exist_ok=True)
        
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                raw = self.serial_conn.readline()
                if not raw: continue
                line = raw.decode('utf-8', errors='ignore').strip()
                if not line: continue
                
                global web_srv
                if web_srv and not isinstance(self.serial_conn, HttpSseSerialBridge):
                    web_srv.broadcast({"type": "serial_data", "data": line})
                
                now = datetime.datetime.now().strftime("%H:%M:%S")
                
                # Check for Receiver logs (+RCV:)
                if line.startswith("+RCV:"):
                    self.process_rx_log(line, now)
                elif "+RCV_ERR: CRC Error!" in line:
                    self.out.write(f"{now} | [WARNING] CRC Error detected!\n")
                    if self.csv_writer and self.current_uuid:
                        iso = datetime.datetime.now().isoformat()
                        self.csv_writer.writerow([iso, "CRC_ERR", "N/A", self.current_uuid, "N/A", "N/A", "N/A"])
                        self.csv_file.flush()
                else:
                    self.out.write(f"{line}\n")
            except Exception as e:
                break

    def process_rx_log(self, line, now_str):
        # Format: +RCV:FRM:0:uuid:*** | SNR:9.50 | RSSI:-45
        parts = line.split(" | ")
        rcv_part = parts[0]
        snr = "N/A"
        rssi = "N/A"
        for p in parts[1:]:
            if p.startswith("SNR:"): snr = p.split(":")[1].strip()
            elif p.startswith("RSSI:"): rssi = p.split(":")[1].strip()
                
        payload = rcv_part[5:]
        tag_map = {"TST": "PRE-TEST", "FRM": "FORM", "STR": "STRESS"}
        mode_tag = tag_map.get(payload[:3], "UNKNOWN")
        
        first_colon = payload.find(':')
        second_colon = payload.find(':', first_colon + 1)
        asterisk = payload.find('*')
        if asterisk == -1: asterisk = len(payload)
            
        uuid_str = "N/A"
        if second_colon != -1 and second_colon < asterisk:
            id_str = payload[first_colon + 1:second_colon]
            uuid_str = payload[second_colon + 1:asterisk]
        else:
            id_str = payload[first_colon + 1:asterisk]
            
        try:
            pkt_id = int(id_str)
        except ValueError:
            self.out.write(f"[RAW RCV] {line}\n")
            return
            
        if uuid_str not in self.session_stats:
            self.session_stats[uuid_str] = {"received": set(), "max": -1}
        
        stats = self.session_stats[uuid_str]
        if pkt_id < stats["max"] - 5 or (pkt_id == 0 and stats["max"] > 0):
            stats["received"].clear()
            stats["max"] = -1
            
        stats["received"].add(pkt_id)
        if pkt_id > stats["max"]: stats["max"] = pkt_id
            
        tot = stats["max"] + 1
        loss = ((tot - len(stats["received"])) / tot * 100.0) if tot > 0 else 0.0
        
        if uuid_str != self.current_uuid:
            if self.csv_file: self.csv_file.close()
            self.current_uuid = uuid_str
            log_path = f"logs/rx_Node_{self.node_name}_session_{self.current_uuid}.csv"
            exists = os.path.exists(log_path)
            self.csv_file = open(log_path, 'a', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            if not exists:
                self.csv_writer.writerow(["Timestamp", "Mode", "PacketID", "UUID", "SNR_dB", "RSSI_dBm", "LossRate"])
                self.csv_file.flush()
            self.out.write(f"\n[INFO] Logging RX data to: {log_path}\n")
            
        iso = datetime.datetime.now().isoformat()
        if mode_tag in ["FORM", "STRESS"] and self.csv_writer:
            self.csv_writer.writerow([iso, mode_tag, pkt_id, uuid_str, snr, rssi, f"{loss:.2f}"])
            self.csv_file.flush()
            
        self.out.write(f"{now_str} | RX_{mode_tag} | ID:{pkt_id} | SNR:{snr} | RSSI:{rssi} | Loss:{loss:.2f}%\n")


class RfTestManagerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LoRa Avionic Link Test & Flashing Manager (Unified Nodes)")
        self.geometry("1400x800")
        
        # TCP Sync Control Frame
        sync_frame = ttk.LabelFrame(self, text="TCP Parameter Sync (Tailscale)", padding=10)
        sync_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(sync_frame, text="Peer IP:").pack(side='left', padx=5)
        self.peer_ip_entry = ttk.Entry(sync_frame, width=20)
        self.peer_ip_entry.pack(side='left', padx=5)
        
        self.btn_sync_conn = ttk.Button(sync_frame, text="Connect", command=self.toggle_sync_connection)
        self.btn_sync_conn.pack(side='left', padx=5)
        
        self.lbl_sync_status = ttk.Label(sync_frame, text="Status: Disconnected", foreground="red")
        self.lbl_sync_status.pack(side='left', padx=10)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tab_flash = ttk.Frame(self.notebook)
        self.tab_dual = ttk.Frame(self.notebook)
        self.tab_analysis = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_flash, text="Flasher")
        self.notebook.add(self.tab_dual, text="Dual Nodes View")
        self.notebook.add(self.tab_analysis, text="Log Analyzer")
        
        self.create_flash_tab()
        
        self.paned_dual = ttk.PanedWindow(self.tab_dual, orient=tk.HORIZONTAL)
        self.paned_dual.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.nodeA = NodePanel(self.paned_dual, "A")
        self.paned_dual.add(self.nodeA, weight=1)
        
        self.nodeB = NodePanel(self.paned_dual, "B")
        self.paned_dual.add(self.nodeB, weight=1)
        
        self.create_analysis_tab()
        
        # Initialize TCP Sync Manager after node panels are ready
        global tcp_sync_mgr
        
        def on_cmd_rcv(cmd):
            for panel in [self.nodeA, self.nodeB]:
                if panel.running and panel.serial_conn:
                    panel.send_raw(cmd, from_sync=True)
                    panel.out.write(f"[TCP Sync] Peer synchronized: {cmd}\n")
                    
                    # Update GUI controls
                    parts = cmd.strip().split()
                    if len(parts) >= 2:
                        prefix = parts[0]
                        val = parts[1]
                        if prefix == 'f':
                            try:
                                mhz = str(int(int(val) / 1E6))
                                panel.dyn_f.set(mhz)
                            except:
                                pass
                        elif prefix == 'b':
                            panel.dyn_b.set(val)
                        elif prefix == 'c':
                            panel.dyn_c.set(val)
                        elif prefix == 'v':
                            panel.dyn_s.set(val)

        def gui_tcp_log(msg):
            print(f"[TCP Sync] {msg}")
            for panel in [self.nodeA, self.nodeB]:
                if panel.running:
                    panel.out.write(f"[TCP Sync] {msg}\n")

        tcp_sync_mgr = TCPSyncManager(port=50077, on_command_received=on_cmd_rcv, log_func=gui_tcp_log)
        
        self.update_sync_ui()
        self.refresh_ports()

    def toggle_sync_connection(self):
        global tcp_sync_mgr
        if not tcp_sync_mgr:
            return
        if not tcp_sync_mgr.is_connected():
            ip = self.peer_ip_entry.get().strip()
            if not ip:
                messagebox.showerror("Error", "Please enter peer's Tailscale IP!")
                return
            self.lbl_sync_status.config(text="Connecting...", foreground="orange")
            tcp_sync_mgr.connect_to_peer(ip)
        else:
            tcp_sync_mgr.disconnect_peer()

    def update_sync_ui(self):
        global tcp_sync_mgr
        if tcp_sync_mgr:
            if tcp_sync_mgr.is_connected():
                peer_ip = tcp_sync_mgr.get_peer_info()
                self.lbl_sync_status.config(text=f"Connected to {peer_ip}", foreground="green")
                self.btn_sync_conn.config(text="Disconnect")
            else:
                self.lbl_sync_status.config(text="Status: Disconnected", foreground="red")
                self.btn_sync_conn.config(text="Connect")
        self.after(1000, self.update_sync_ui)
        
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            ports = ["No devices found"]
            
        self.flash_port_cb['values'] = ports
        self.nodeA.port_cb['values'] = ports
        self.nodeB.port_cb['values'] = ports
        
        if ports and ports[0] != "No devices found":
            self.flash_port_cb.current(0)
            self.nodeA.port_cb.current(0)
            if len(ports) > 1:
                self.nodeB.port_cb.current(1)
            else:
                self.nodeB.port_cb.current(0)
            
    # --- FLASHER TAB ---
    def create_flash_tab(self):
        frame = ttk.Frame(self.tab_flash, padding=10)
        frame.pack(fill='both', expand=True)
        
        ctrl_frame = ttk.LabelFrame(frame, text="Flash rfTestV6.cpp", padding=10)
        ctrl_frame.pack(fill='x', pady=5)
        
        ttk.Label(ctrl_frame, text="Port:").grid(row=0, column=0, sticky='w', pady=2)
        self.flash_port_cb = ttk.Combobox(ctrl_frame, width=30)
        self.flash_port_cb.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(ctrl_frame, text="Refresh Ports", command=self.refresh_ports).grid(row=0, column=2, padx=5, pady=2)
        
        self.btn_flash = ttk.Button(ctrl_frame, text="Flash Firmware", command=self.start_flash_thread)
        self.btn_flash.grid(row=1, column=0, columnspan=3, pady=10)
        
        self.flash_console = scrolledtext.ScrolledText(frame, state='normal', height=20, bg='black', fg='lightgreen', font=('Consolas', 11))
        self.flash_console.pack(fill='both', expand=True, pady=5)
        self.flash_out = ThreadSafeConsole(self.flash_console)

    def start_flash_thread(self):
        self.btn_flash.config(state='disabled')
        self.flash_console.delete('1.0', tk.END)
        threading.Thread(target=self.run_flash, daemon=True).start()

    def run_flash(self):
        try:
            port = self.flash_port_cb.get()            
            if "No devices found" in port or not port:
                self.flash_out.write("[ERROR] Invalid port selected.\n")
                return
                
            src_dir = os.path.abspath('src')
            os.makedirs(src_dir, exist_ok=True)
            
            for filename in os.listdir(src_dir):
                if filename.endswith('.cpp'):
                    os.remove(os.path.join(src_dir, filename))
                    
            master_file = "rfTestV6.cpp"
            sandbox_file = os.path.join(src_dir, master_file)
            
            if not os.path.exists(master_file):
                self.flash_out.write(f"[ERROR] Master file {master_file} not found in root!\n")
                return
                
            shutil.copy2(master_file, sandbox_file)
            
            self.flash_out.write(f"[INFO] Uploading rfTestV6 to {port}...\n")
            
            cmd = ["pio", "run", "-t", "upload", "--upload-port", port]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            for line in process.stdout:
                self.flash_out.write(line)
            
            process.wait()
            if process.returncode == 0:
                self.flash_out.write(f"\n[SUCCESS] Flashing completed!\n")
            else:
                self.flash_out.write(f"\n[ERROR] Flashing failed with code {process.returncode}\n")
        except Exception as e:
            self.flash_out.write(f"[ERROR] {e}\n")
        finally:
            self.flash_console.after(0, lambda: self.btn_flash.config(state='normal'))

    # --- ANALYSIS TAB ---
    def create_analysis_tab(self):
        frame = ttk.Frame(self.tab_analysis, padding=10)
        frame.pack(fill='both', expand=True)
        
        ctrl = ttk.LabelFrame(frame, text="Log Selection", padding=10)
        ctrl.pack(fill='x', pady=5)
        
        self.log_cb = ttk.Combobox(ctrl, width=50)
        self.log_cb.grid(row=0, column=0, padx=5)
        ttk.Button(ctrl, text="Refresh Logs", command=self.refresh_logs).grid(row=0, column=1, padx=5)
        ttk.Button(ctrl, text="Analyze", command=self.analyze_selected_log).grid(row=0, column=2, padx=5)
        
        self.analysis_console = scrolledtext.ScrolledText(frame, height=20, bg='white', fg='black', font=('Consolas', 11))
        self.analysis_console.pack(fill='both', expand=True, pady=5)
        
        self.refresh_logs()

    def refresh_logs(self):
        if not os.path.exists('logs'):
            os.makedirs('logs')
        files = [f for f in os.listdir('logs') if f.endswith('.csv')]
        self.log_cb['values'] = files
        if files:
            self.log_cb.current(0)

    def analyze_selected_log(self):
        sel = self.log_cb.get()
        if not sel:
            return
        
        filepath = os.path.join('logs', sel)
        self.analysis_console.delete('1.0', tk.END)
        self.analysis_console.insert(tk.END, f"Analyzing {sel}...\n\n")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                packet_ids = set()
                snr_list = []
                rssi_list = []
                crc_errors = 0
                
                for row in reader:
                    if row.get('Mode') == 'CRC_ERR':
                        crc_errors += 1
                        continue
                    if 'PacketID' in row:
                        try: packet_ids.add(int(row['PacketID']))
                        except: pass
                    if 'SNR_dB' in row and row['SNR_dB'] != 'N/A':
                        try: snr_list.append(float(row['SNR_dB']))
                        except: pass
                    if 'RSSI_dBm' in row and row['RSSI_dBm'] != 'N/A':
                        try: rssi_list.append(float(row['RSSI_dBm']))
                        except: pass
                        
                if not packet_ids:
                    self.analysis_console.insert(tk.END, "No valid Packet IDs found.\n")
                    return
                    
                max_id = max(packet_ids)
                total_expected = max_id + 1
                total_received = len(packet_ids)
                lost_count = total_expected - total_received
                missed = lost_count - crc_errors if lost_count >= crc_errors else 0
                loss_rate = (lost_count / total_expected * 100) if total_expected > 0 else 0
                
                avg_snr = sum(snr_list)/len(snr_list) if snr_list else 0
                avg_rssi = sum(rssi_list)/len(rssi_list) if rssi_list else 0
                
                rep = (
                    "========================================\n"
                    "          ANALYSIS REPORT\n"
                    "========================================\n"
                    f"  Total Expected Packets : {total_expected}\n"
                    f"  Valid Received Packets : {total_received}\n"
                    f"  CRC Error Packets      : {crc_errors}\n"
                    f"  Completely Missed      : {missed}\n"
                    f"  Total Lost Packets     : {lost_count}\n"
                    f"  Packet Loss Rate       : {loss_rate:.2f} %\n"
                    "----------------------------------------\n"
                    f"  Average SNR            : {avg_snr:.2f} dB\n"
                    f"  Average RSSI           : {avg_rssi:.2f} dBm\n"
                    "========================================\n"
                )
                self.analysis_console.insert(tk.END, rep)
        except Exception as e:
            self.analysis_console.insert(tk.END, f"Error: {e}\n")

if __name__ == "__main__":
    from web_server import start_web_server
    web_srv = start_web_server(8080, os.path.dirname(os.path.abspath(__file__)), get_web_status, execute_web_action)
    
    app = RfTestManagerGUI()
    gui_app = app
    app.mainloop()

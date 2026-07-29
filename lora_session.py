#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LoRaSessionEngine & Transport Seam — Unified Hardware Communication & Log Adapter.
Provides an abstract Transport seam (SerialTransport, MockTransport) and manages
background reading threads, thread safety, and standardized CSV log file generation.
"""

import os
import csv
import time
import queue
import threading
import datetime
from abc import ABC, abstractmethod
from typing import Optional, Callable, List
from lora_telemetry import LoRaTelemetryEngine, TelemetryEvent, SessionStats
from lora_codec import LoRaCommandCodec

class Transport(ABC):
    @abstractmethod
    def is_open(self) -> bool:
        pass

    @abstractmethod
    def read_line(self) -> str:
        pass

    @abstractmethod
    def write_line(self, line: str) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

class SerialTransport(Transport):
    def __init__(self, serial_obj):
        self.ser = serial_obj

    def is_open(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def read_line(self) -> str:
        if not self.is_open():
            return ""
        raw = self.ser.readline()
        if not raw:
            return ""
        return raw.decode('utf-8', errors='ignore').strip()

    def write_line(self, line: str) -> None:
        if self.is_open():
            self.ser.write((line.strip() + '\n').encode('utf-8'))

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

class MockTransport(Transport):
    def __init__(self):
        self._is_open = True
        self.written_lines: List[str] = []
        self.read_queue: queue.Queue = queue.Queue()

    def is_open(self) -> bool:
        return self._is_open

    def read_line(self) -> str:
        try:
            return self.read_queue.get(timeout=0.05)
        except queue.Empty:
            return ""

    def write_line(self, line: str) -> None:
        self.written_lines.append(line.strip())

    def close(self) -> None:
        self._is_open = False

class LoRaSessionEngine:
    def __init__(self, transport: Optional[Transport] = None, log_dir: str = "logs"):
        self.transport = transport
        self.log_dir = log_dir
        self.telemetry = LoRaTelemetryEngine()
        self.running = False
        self.lock = threading.Lock()

        self._read_thread: Optional[threading.Thread] = None
        self.csv_file = None
        self.csv_writer = None
        self.current_uuid: Optional[str] = None
        self.on_event_callbacks: List[Callable[[TelemetryEvent], None]] = []

    def add_event_listener(self, callback: Callable[[TelemetryEvent], None]):
        self.on_event_callbacks.append(callback)

    def start_session(self, session_uuid: Optional[str] = None, csv_prefix: str = "session"):
        os.makedirs(self.log_dir, exist_ok=True)
        self.current_uuid = session_uuid or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.telemetry.reset()
        
        csv_filename = os.path.join(self.log_dir, f"{csv_prefix}_{self.current_uuid}.csv")
        self.csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Timestamp", "Status", "Pkt_ID", "UUID", "ToA_ms", "RSSI", "SNR"])
        self.csv_file.flush()

        self.running = True
        if self.transport and self.transport.is_open():
            self._read_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._read_thread.start()

    def _reader_loop(self):
        while self.running and self.transport and self.transport.is_open():
            try:
                line = self.transport.read_line()
                if not line:
                    continue
                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                event = self.telemetry.parse_line(line, now_str)
                event.uuid_str = self.current_uuid

                # Log to CSV if appropriate
                if event.event_type in ('RCV', 'CRC_ERR', 'TX_LOG') and self.csv_writer:
                    iso_time = datetime.datetime.now().isoformat()
                    with self.lock:
                        self.csv_writer.writerow([
                            iso_time,
                            event.event_type,
                            event.pkt_id if event.pkt_id is not None else "N/A",
                            self.current_uuid,
                            event.toa_ms if event.toa_ms is not None else "N/A",
                            event.rssi if event.rssi is not None else "N/A",
                            event.snr if event.snr is not None else "N/A"
                        ])
                        self.csv_file.flush()

                # Dispatch event to UI/CLI listeners
                for cb in self.on_event_callbacks:
                    try:
                        cb(event)
                    except Exception:
                        pass

            except Exception:
                time.sleep(0.05)

    def send_command(self, cmd_str: str):
        with self.lock:
            if self.transport and self.transport.is_open():
                self.transport.write_line(cmd_str)

    def stop_session(self):
        self.running = False
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1.0)
        with self.lock:
            if self.csv_file:
                try:
                    self.csv_file.close()
                except Exception:
                    pass
                self.csv_file = None

    def get_stats(self) -> SessionStats:
        return self.telemetry.get_stats()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LoRaTelemetryEngine — Telemetry Protocol Parser & Statistics Analyzer Deep Module.
Pure stateful data processing for parsing receiver lines, transmitter logs, CRC errors,
sequence tracking, and CSV log analysis.
"""

import re
import csv
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class TelemetryEvent:
    event_type: str  # 'RCV', 'CRC_ERR', 'TX_LOG', 'RAW'
    timestamp: str
    pkt_id: Optional[int] = None
    sent_ts: Optional[str] = None
    rssi: Optional[int] = None
    snr: Optional[float] = None
    payload_len: Optional[int] = None
    toa_ms: Optional[float] = None
    uuid_str: Optional[str] = None
    raw_line: str = ""

@dataclass
class SessionStats:
    total_received: int = 0
    total_crc_errors: int = 0
    min_id: Optional[int] = None
    max_id: Optional[int] = None
    expected_count: int = 0
    lost_count: int = 0
    loss_rate: float = 0.0
    rssi_avg: float = 0.0
    snr_avg: float = 0.0

class LoRaTelemetryEngine:
    def __init__(self):
        self.received_ids = set()
        self.total_received = 0
        self.total_crc_errors = 0
        self.rssi_list = []
        self.snr_list = []

    def reset(self):
        self.received_ids.clear()
        self.total_received = 0
        self.total_crc_errors = 0
        self.rssi_list.clear()
        self.snr_list.clear()

    def parse_line(self, line: str, now_str: Optional[str] = None) -> TelemetryEvent:
        """Parse raw serial output into a structured TelemetryEvent."""
        if now_str is None:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

        line_str = line.strip()

        # 1. Receiver packet match: +RCV:...
        if line_str.startswith("+RCV:"):
            # Example: +RCV: ID:42 | Sent:12:34:56 | SNR:9.5 | RSSI:-85 | Len:255
            event = TelemetryEvent(event_type='RCV', timestamp=now_str, raw_line=line_str)
            
            id_match = re.search(r"ID:(\d+)", line_str)
            if id_match:
                pkt_id = int(id_match.group(1))
                event.pkt_id = pkt_id
                self.received_ids.add(pkt_id)

            snr_match = re.search(r"SNR:([-\d\.]+)", line_str)
            if snr_match:
                event.snr = float(snr_match.group(1))
                self.snr_list.append(event.snr)

            rssi_match = re.search(r"RSSI:([-\d\.]+)", line_str)
            if rssi_match:
                event.rssi = int(float(rssi_match.group(1)))
                self.rssi_list.append(event.rssi)

            len_match = re.search(r"Len:(\d+)", line_str)
            if len_match:
                event.payload_len = int(len_match.group(1))

            self.total_received += 1
            return event

        # 2. CRC Error match
        elif "+RCV_ERR: CRC Error!" in line_str:
            self.total_crc_errors += 1
            return TelemetryEvent(event_type='CRC_ERR', timestamp=now_str, raw_line=line_str)

        # 3. Transmitter TX log match
        elif line_str.startswith(("[PRE]", "[STRESS]", "[FORM]")):
            # Example: [FORM] Sent ID: 10, Len: 255 Bytes, ToA: 154.2 ms
            event = TelemetryEvent(event_type='TX_LOG', timestamp=now_str, raw_line=line_str)
            id_match = re.search(r"ID:\s*(\d+)", line_str)
            if id_match:
                event.pkt_id = int(id_match.group(1))
            len_match = re.search(r"Len:\s*(\d+)", line_str)
            if len_match:
                event.payload_len = int(len_match.group(1))
            toa_match = re.search(r"ToA:\s*([-\d\.]+)", line_str)
            if toa_match:
                event.toa_ms = float(toa_match.group(1))
            return event

        # 4. Fallback raw line
        return TelemetryEvent(event_type='RAW', timestamp=now_str, raw_line=line_str)

    def get_stats(self) -> SessionStats:
        """Compute accumulated statistics for the session."""
        stats = SessionStats(
            total_received=self.total_received,
            total_crc_errors=self.total_crc_errors
        )
        if self.received_ids:
            stats.min_id = min(self.received_ids)
            stats.max_id = max(self.received_ids)
            stats.expected_count = stats.max_id - stats.min_id + 1
            stats.lost_count = max(0, stats.expected_count - len(self.received_ids))
            stats.loss_rate = (stats.lost_count / stats.expected_count * 100.0) if stats.expected_count > 0 else 0.0

        if self.rssi_list:
            stats.rssi_avg = sum(self.rssi_list) / len(self.rssi_list)
        if self.snr_list:
            stats.snr_avg = sum(self.snr_list) / len(self.snr_list)

        return stats

    @classmethod
    def analyze_log_file(cls, csv_path: str) -> Dict[str, Any]:
        """Analyze a CSV log file and return summary metrics."""
        received_ids = set()
        total_rows = 0
        crc_errors = 0
        rssi_list = []
        snr_list = []

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if not row or len(row) < 3:
                    continue
                total_rows += 1
                status = row[1] if len(row) > 1 else ""
                if status == "CRC_ERR":
                    crc_errors += 1
                    continue

                try:
                    pkt_id = int(row[2])
                    received_ids.add(pkt_id)
                except (ValueError, IndexError):
                    pass

                try:
                    if len(row) >= 6 and row[5] != "N/A":
                        rssi_list.append(float(row[5]))
                    if len(row) >= 7 and row[6] != "N/A":
                        snr_list.append(float(row[6]))
                except ValueError:
                    pass

        min_id = min(received_ids) if received_ids else 0
        max_id = max(received_ids) if received_ids else 0
        expected = (max_id - min_id + 1) if received_ids else 0
        lost = max(0, expected - len(received_ids))
        loss_rate = (lost / expected * 100.0) if expected > 0 else 0.0

        return {
            "total_rows": total_rows,
            "received_unique": len(received_ids),
            "crc_errors": crc_errors,
            "min_id": min_id,
            "max_id": max_id,
            "expected_count": expected,
            "lost_count": lost,
            "loss_rate": loss_rate,
            "rssi_avg": (sum(rssi_list) / len(rssi_list)) if rssi_list else 0.0,
            "snr_avg": (sum(snr_list) / len(snr_list)) if snr_list else 0.0
        }

#!/usr/bin/env python3
import unittest
from lora_telemetry import LoRaTelemetryEngine, TelemetryEvent

class TestLoRaTelemetryEngine(unittest.TestCase):
    def test_parse_line_rcv(self):
        engine = LoRaTelemetryEngine()
        line = "+RCV: ID:42 | Sent:12:34:56 | SNR:9.5 | RSSI:-85 | Len:255"
        event = engine.parse_line(line, "12:34:57")
        self.assertEqual(event.event_type, 'RCV')
        self.assertEqual(event.pkt_id, 42)
        self.assertEqual(event.snr, 9.5)
        self.assertEqual(event.rssi, -85)
        self.assertEqual(event.payload_len, 255)

        stats = engine.get_stats()
        self.assertEqual(stats.total_received, 1)
        self.assertEqual(stats.min_id, 42)
        self.assertEqual(stats.max_id, 42)
        self.assertEqual(stats.rssi_avg, -85.0)

    def test_parse_line_tx_log(self):
        engine = LoRaTelemetryEngine()
        line = "[FORM] Sent ID: 10, Len: 255 Bytes, ToA: 154.2 ms"
        event = engine.parse_line(line)
        self.assertEqual(event.event_type, 'TX_LOG')
        self.assertEqual(event.pkt_id, 10)
        self.assertEqual(event.payload_len, 255)
        self.assertEqual(event.toa_ms, 154.2)

    def test_sequence_loss_calculation(self):
        engine = LoRaTelemetryEngine()
        engine.parse_line("+RCV: ID:1 | SNR:10 | RSSI:-80")
        engine.parse_line("+RCV: ID:3 | SNR:10 | RSSI:-80")
        engine.parse_line("+RCV: ID:5 | SNR:10 | RSSI:-80")

        stats = engine.get_stats()
        self.assertEqual(stats.min_id, 1)
        self.assertEqual(stats.max_id, 5)
        self.assertEqual(stats.expected_count, 5)
        self.assertEqual(stats.total_received, 3)
        self.assertEqual(stats.lost_count, 2)
        self.assertEqual(stats.loss_rate, 40.0)

if __name__ == '__main__':
    unittest.main()

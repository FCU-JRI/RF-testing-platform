#!/usr/bin/env python3
import os
import time
import unittest
from lora_session import LoRaSessionEngine, MockTransport

class TestLoRaSessionEngine(unittest.TestCase):
    def setUp(self):
        self.log_dir = "tmp_test_logs"

    def tearDown(self):
        if os.path.exists(self.log_dir):
            for f in os.listdir(self.log_dir):
                os.remove(os.path.join(self.log_dir, f))
            os.rmdir(self.log_dir)

    def test_mock_session_flow(self):
        mock_transport = MockTransport()
        engine = LoRaSessionEngine(transport=mock_transport, log_dir=self.log_dir)

        received_events = []
        engine.add_event_listener(lambda evt: received_events.append(evt))

        engine.start_session(session_uuid="test_123", csv_prefix="rx_test")

        # Push mock serial telemetry into transport queue
        mock_transport.read_queue.put("+RCV: ID:10 | SNR:8.5 | RSSI:-75")
        mock_transport.read_queue.put("+RCV: ID:11 | SNR:9.0 | RSSI:-72")
        time.sleep(0.2)

        engine.send_command("v 7")
        self.assertIn("v 7", mock_transport.written_lines)

        engine.stop_session()

        self.assertGreaterEqual(len(received_events), 2)
        stats = engine.get_stats()
        self.assertEqual(stats.total_received, 2)
        self.assertEqual(stats.min_id, 10)
        self.assertEqual(stats.max_id, 11)

if __name__ == '__main__':
    unittest.main()

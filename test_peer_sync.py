#!/usr/bin/env python3
import time
import unittest
from peer_sync import PeerSyncManager

class TestPeerSyncManager(unittest.TestCase):
    def test_peer_sync_loop(self):
        received_cmds = []

        # Start host A and host B peer managers
        srv_a = PeerSyncManager(port=59077, on_param_received=lambda cmd: received_cmds.append(('A', cmd)))
        srv_b = PeerSyncManager(port=59078, on_param_received=lambda cmd: received_cmds.append(('B', cmd)))
        time.sleep(0.2)

        # A connects to B
        connected = srv_a.connect_peer('127.0.0.1', port=59078)
        self.assertTrue(connected)
        time.sleep(0.2)

        # Send parameter commands from A to B
        srv_a.send_param_cmd("f 433000000")
        srv_a.send_param_cmd("v 8")
        time.sleep(0.3)

        srv_a.close()
        srv_b.close()

        self.assertIn(('B', 'f 433000000'), received_cmds)
        self.assertIn(('B', 'v 8'), received_cmds)

if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
import unittest
from lora_codec import LoRaCommandCodec

class TestLoRaCommandCodec(unittest.TestCase):
    def test_freq_mhz_to_hz(self):
        self.assertEqual(LoRaCommandCodec.freq_mhz_to_hz(433.0), 433000000)
        self.assertEqual(LoRaCommandCodec.freq_mhz_to_hz(915), 915000000)

    def test_encode_rf_config(self):
        cmds = LoRaCommandCodec.encode_rf_config(freq_mhz=433.0, bw_hz=125000, cr=6, sf=7, payload_len=255)
        self.assertEqual(cmds, ["f 433000000", "b 125000", "c 6", "v 7", "l 255"])

    def test_encode_test_start(self):
        self.assertEqual(LoRaCommandCodec.encode_test_start('formal', sf=7), ["7"])
        self.assertEqual(LoRaCommandCodec.encode_test_start('pre', sf=8), ["p 8"])
        self.assertEqual(LoRaCommandCodec.encode_test_start('stress', sf=7, interval_ms=150), ["s 7 150"])
        self.assertEqual(LoRaCommandCodec.encode_test_start('stop'), ["x"])

    def test_safe_interval_clamping(self):
        self.assertEqual(LoRaCommandCodec.get_safe_interval(7), 150)
        self.assertEqual(LoRaCommandCodec.get_safe_interval(10), 850)
        self.assertEqual(LoRaCommandCodec.get_safe_interval(12), 3000)

if __name__ == '__main__':
    unittest.main()

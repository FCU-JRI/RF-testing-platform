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

    def test_is_rf_param_cmd(self):
        self.assertTrue(LoRaCommandCodec.is_rf_param_cmd("f 433000000"))
        self.assertTrue(LoRaCommandCodec.is_rf_param_cmd("b 125000"))
        self.assertTrue(LoRaCommandCodec.is_rf_param_cmd("c 6"))
        self.assertTrue(LoRaCommandCodec.is_rf_param_cmd("v 7"))
        self.assertTrue(LoRaCommandCodec.is_rf_param_cmd("l 255"))
        self.assertFalse(LoRaCommandCodec.is_rf_param_cmd("s 7 150"))
        self.assertFalse(LoRaCommandCodec.is_rf_param_cmd("x"))

if __name__ == '__main__':
    unittest.main()

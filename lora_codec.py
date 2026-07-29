#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LoRaCommandCodec — Serial Protocol & Parameter Validator Deep Module.
Encapsulates RF command encoding, unit conversions (MHz <-> Hz), safe SF intervals,
and parameter validation rules for the ESP32 LoRa transceiver.
"""

from typing import List, Dict, Any, Optional

class LoRaCommandCodec:
    MIN_SF = 6
    MAX_SF = 12
    MIN_PAYLOAD_LEN = 45
    MAX_PAYLOAD_LEN = 255

    SAFE_INTERVALS = {
        6: 50,
        7: 150,
        8: 250,
        9: 450,
        10: 850,
        11: 1600,
        12: 3000
    }

    RF_PARAM_PREFIXES = ('f ', 'b ', 'c ', 'v ', 'l ')

    @classmethod
    def is_rf_param_cmd(cls, cmd: str) -> bool:
        """Return True only for RF parameter commands that should sync to peer nodes."""
        c = cmd.strip()
        return any(c.startswith(p) for p in cls.RF_PARAM_PREFIXES)

    @classmethod
    def get_safe_interval(cls, sf: int) -> int:
        """Return the safe test packet interval (in ms) for a given Spreading Factor."""
        return cls.SAFE_INTERVALS.get(int(sf), 150)

    @classmethod
    def freq_mhz_to_hz(cls, freq_mhz: float) -> int:
        """Convert frequency in MHz (e.g. 433.0 or 915) to Hz integer."""
        return int(float(freq_mhz) * 1e6)

    @classmethod
    def encode_rf_config(
        cls,
        freq_mhz: Optional[float] = None,
        bw_hz: Optional[int] = None,
        cr: Optional[int] = None,
        sf: Optional[int] = None,
        payload_len: Optional[int] = None
    ) -> List[str]:
        """Format and validate RF parameter configuration serial commands."""
        cmds = []
        if freq_mhz is not None:
            hz = cls.freq_mhz_to_hz(freq_mhz)
            cmds.append(f"f {hz}")
        if bw_hz is not None:
            cmds.append(f"b {int(bw_hz)}")
        if cr is not None:
            cmds.append(f"c {int(cr)}")
        if sf is not None:
            sf_int = int(sf)
            if not (cls.MIN_SF <= sf_int <= cls.MAX_SF):
                raise ValueError(f"Spreading Factor must be between {cls.MIN_SF} and {cls.MAX_SF}")
            cmds.append(f"v {sf_int}")
        if payload_len is not None:
            l_int = int(payload_len)
            if not (cls.MIN_PAYLOAD_LEN <= l_int <= cls.MAX_PAYLOAD_LEN):
                raise ValueError(f"Payload length must be between {cls.MIN_PAYLOAD_LEN} and {cls.MAX_PAYLOAD_LEN}")
            cmds.append(f"l {l_int}")
        return cmds

    @classmethod
    def encode_test_start(
        cls,
        test_type: str,
        sf: int = 7,
        interval_ms: Optional[int] = None,
        uuid_str: Optional[str] = None
    ) -> List[str]:
        """Format test execution commands ('formal', 'pre', 'stress', 'stop')."""
        cmds = []
        if uuid_str:
            cmds.append(f"u {uuid_str}")

        t = test_type.lower()
        if t == 'stop':
            cmds.append("x")
        elif t == 'formal':
            cmds.append(f"{int(sf)}")
        elif t == 'pre':
            cmds.append(f"p {int(sf)}")
        elif t == 'stress':
            interval = interval_ms if interval_ms is not None else cls.get_safe_interval(sf)
            cmds.append(f"s {int(sf)} {int(interval)}")
        else:
            raise ValueError(f"Unknown test type: {test_type}")
        return cmds

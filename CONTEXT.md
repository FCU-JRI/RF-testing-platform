# Context & Glossary: RF Testing Platform

## Ubiquitous Language

- **RF Test Manager**: The main Python application (CLI & Tkinter GUI) for controlling ESP32-based LoRa test nodes, flashing firmware, configuring RF parameters, and logging test data.
- **Node A / Node B**: Local serial test slots representing ESP32 LoRa transmitter/receiver hardware nodes connected via USB COM ports.
- **RF Parameters**: Modulation settings (`Frequency`, `Bandwidth`, `Coding Rate`, `Spreading Factor`, `Payload Length`) transmitted to ESP32 over serial.
- **Serial Connection**: Direct USB UART serial interface between the host computer and an ESP32 hardware module.
- **PeerSyncSocket**: Machine-to-machine TCP socket protocol (`peer_sync.py`) for synchronizing RF parameters across IP-connected stations.
- **Deep Modules**: Pure, decoupled domain architecture modules:
  - `LoRaCommandCodec` (`lora_codec.py`): Protocol parameter validation & MHz/Hz encoding.
  - `LoRaTelemetryEngine` (`lora_telemetry.py`): Stateful telemetry parsing & CSV loss analysis.
  - `LoRaSessionEngine` (`lora_session.py`): Threaded session management & `Transport` seam.

## Architecture Decision Records

- [ADR 0001: Deprecate Legacy Peer IP TCP Sync](file:///Users/hekote/Documents/PlatformIO/Projects/P2026_rfTest/docs/adr/0001-remove-peer-ip-tcp-sync.md)
- [ADR 0002: Peer Sync Socket & GUI/UX Overhaul](file:///Users/hekote/Documents/PlatformIO/Projects/P2026_rfTest/docs/adr/0002-peer-sync-socket-and-gui-ux-overhaul.md)

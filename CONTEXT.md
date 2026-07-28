# Context & Glossary: RF Testing Platform

## Ubiquitous Language

- **RF Test Manager**: The main Python application (CLI & Tkinter GUI) for controlling ESP32-based LoRa test nodes, flashing firmware, configuring RF parameters, and logging test data.
- **Node A / Node B**: Local serial test slots representing ESP32 LoRa transmitter/receiver hardware nodes connected via USB COM ports.
- **RF Parameters**: Modulation settings (`Frequency`, `Bandwidth`, `Coding Rate`, `Spreading Factor`, `Payload Length`) transmitted to ESP32 over serial.
- **Serial Connection**: Direct USB UART serial interface between the host computer and an ESP32 hardware module.

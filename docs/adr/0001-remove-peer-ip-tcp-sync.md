# Remove Peer IP / TCP Parameter Sync from Desktop GUI

We decided to completely remove the Peer IP input and Tailscale TCP Parameter Sync block from the desktop Tkinter GUI (`rf_test_manager_gui.py`). Test operations are conducted via direct local USB Serial connections to ESP32 test nodes; remote TCP sync added unnecessary UI clutter, background thread overhead, and user confusion without providing operational value in single-machine testing setups.

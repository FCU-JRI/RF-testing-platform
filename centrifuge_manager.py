import os
import sys
import time
import subprocess

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[INFO] 'pyserial' is required. Please install it using: pip install pyserial")
    sys.exit(1)

DEFAULT_PORT = None

def scan_serial_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial devices detected.")
        return None
    print("\n=== Active Serial Ports ===")
    for idx, p in enumerate(ports, start=1):
        print(f"  {idx}) {p.device} | {p.description}")
    
    choice = input(f"\nSelect port number (1-{len(ports)}) [Default: 1]: ").strip()
    idx = int(choice) - 1 if choice and choice.isdigit() else 0
    if 0 <= idx < len(ports):
        return ports[idx].device
    return ports[0].device

def flash_firmware():
    global DEFAULT_PORT
    if not DEFAULT_PORT:
        DEFAULT_PORT = scan_serial_ports()
        if not DEFAULT_PORT: return

    src_dir = os.path.abspath('src')
    os.makedirs(src_dir, exist_ok=True)
    
    for filename in os.listdir(src_dir):
        if filename.endswith('.cpp'):
            os.remove(os.path.join(src_dir, filename))
            
    import shutil
    shutil.copy2('centrifuge_test.cpp', os.path.join(src_dir, 'centrifuge_test.cpp'))
    
    print("\n[INFO] Starting compile and upload...")
    print(f"[INFO] Upload Port: {DEFAULT_PORT}")
    
    cmd = ["pio", "run", "-t", "upload", "--upload-port", DEFAULT_PORT]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='')
    process.wait()
    if process.returncode == 0:
        print("\n[SUCCESS] Flashing completed!")
    else:
        print(f"\n[ERROR] Flashing failed with code: {process.returncode}")

def dump_data():
    global DEFAULT_PORT
    if not DEFAULT_PORT:
        DEFAULT_PORT = scan_serial_ports()
        if not DEFAULT_PORT: return
        
    print(f"\n[INFO] Connecting to {DEFAULT_PORT}...")
    try:
        ser = serial.Serial(DEFAULT_PORT, 115200, timeout=2.0)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return
        
    time.sleep(2)
    ser.reset_input_buffer()
    
    print("[INFO] Sending DUMP command to Avionics...")
    ser.write(b"DUMP\n")
    
    log_path = "washing_machine_results.csv"
    print(f"[INFO] Downloading data to {log_path}...")
    
    received_lines = 0
    with open(log_path, 'w', encoding='utf-8') as f:
        while True:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line == "EOF":
                    print("\n[SUCCESS] Data download complete!")
                    break
                elif line == "NO_DATA":
                    print("\n[WARNING] No data file found on SD card.")
                    break
                elif line:
                    if ">>>" not in line: # Ignore firmware debug prints
                        f.write(line + '\n')
                        received_lines += 1
                        if received_lines % 100 == 0:
                            print(f"\r[STATUS] Downloaded {received_lines} lines...", end='')
            except KeyboardInterrupt:
                print("\n[INFO] Download interrupted by user.")
                break
    print(f"\n[INFO] Total {received_lines} records saved.")
    ser.close()

def clear_data():
    global DEFAULT_PORT
    if not DEFAULT_PORT:
        DEFAULT_PORT = scan_serial_ports()
        if not DEFAULT_PORT: return
        
    print(f"\n[INFO] Connecting to {DEFAULT_PORT}...")
    try:
        ser = serial.Serial(DEFAULT_PORT, 115200, timeout=2.0)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return
        
    time.sleep(2)
    print("[INFO] Sending CLEAR command to Avionics...")
    ser.write(b"CLEAR\n")
    
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line == "CLEARED":
            print("\n[SUCCESS] SD Card data cleared!")
            break
        elif not line:
            print("\n[ERROR] No response from Avionics.")
            break
    ser.close()

def main():
    while True:
        print("\n" + "=" * 64)
        print("     Washing Machine Centrifuge Test Manager (Avionics)     ")
        print("=" * 64)
        print("  1) Flash Centrifuge Test Firmware")
        print("  2) Download Test Data from SD Card via USB (DUMP)")
        print("  3) Clear SD Card Data (CLEAR)")
        print("  4) Exit")
        print("=" * 64)
        
        choice = input("\nEnter option (1-4): ").strip()
        
        if choice == '1':
            flash_firmware()
        elif choice == '2':
            dump_data()
        elif choice == '3':
            clear_data()
        elif choice == '4':
            break
        else:
            print("[ERROR] Invalid choice.")

if __name__ == "__main__":
    main()

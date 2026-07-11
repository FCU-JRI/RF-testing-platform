#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LoRa Avionic Link Test & Flashing Manager
-----------------------------------------
This tool automates:
1. Scanning serial ports.
2. Modifying carrier frequencies in code and flashing via PlatformIO.
3. Generating UUIDs, starting test sessions on the Sender, and logging sent packets.
4. Parsing incoming LoRa packets on the Receiver and logging them to CSV files.
"""

import os
import sys
import time
import uuid
import re
import csv
import subprocess
import datetime

import serial
import serial.tools.list_ports
# Default configuration parameters
DEFAULT_PORT = None
AVAILABLE_PORTS = []


def scan_serial_ports():
    """Scans and lists active serial ports."""
    global AVAILABLE_PORTS
    ports = list(serial.tools.list_ports.comports())
    AVAILABLE_PORTS = [p.device for p in ports]
    print("\n=== Active Serial Ports ===")
    if not ports:
        print("No serial devices detected.")
        return []
    for idx, p in enumerate(ports, start=1):
        desc = p.description if p.description else "N/A"
        hwid = p.hwid if p.hwid else "N/A"
        print(f"  {idx}) {p.device} | Description: {desc} | HWID: {hwid}")
    return AVAILABLE_PORTS


def select_port():
    """Prompts user to select a port from the scanned list."""
    global DEFAULT_PORT
    ports = scan_serial_ports()
    if not ports:
        return None
    
    choice = input(f"\nSelect port number (1-{len(ports)}) [Default: 1]: ").strip()
    if not choice:
        DEFAULT_PORT = ports[0]
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                DEFAULT_PORT = ports[idx]
            else:
                print("[WARNING] Invalid selection. Using default first port.")
                DEFAULT_PORT = ports[0]
        except ValueError:
            print("[WARNING] Invalid selection. Using default first port.")
            DEFAULT_PORT = ports[0]
            
    print(f"[INFO] Selected Port: {DEFAULT_PORT}")
    return DEFAULT_PORT


def flash_firmware():
    """Handles file sandboxing, frequency switching, compilation, and uploading via PlatformIO."""
    global DEFAULT_PORT
    if not DEFAULT_PORT:
        DEFAULT_PORT = select_port()
        if not DEFAULT_PORT:
            print("[ERROR] No port selected. Flashing aborted.")
            return False
            

    # Manage the PlatformIO 'src/' compilation directory
    src_dir = os.path.abspath('src')
    os.makedirs(src_dir, exist_ok=True)
    
    # Clean up the src folder to avoid multiple setups/loops
    for filename in os.listdir(src_dir):
        if filename.endswith('.cpp'):
            os.remove(os.path.join(src_dir, filename))
            
    # Source master file
    master_file = "rfTestV6.cpp"
    sandbox_file = os.path.join(src_dir, master_file)
    
    if not os.path.exists(master_file):
        print(f"[ERROR] Master file {master_file} not found in workspace root!")
        return False
        
    import shutil
    shutil.copy2(master_file, sandbox_file)
    
    print(f"\n[INFO] Starting compile and upload for: rfTestV6")
    print(f"[INFO] Upload Port: {DEFAULT_PORT}")
    print("[INFO] Running: pio run -t upload\n")
    
    # Execute PlatformIO upload
    cmd = ["pio", "run", "-t", "upload", "--upload-port", DEFAULT_PORT]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')
        process.wait()
        if process.returncode == 0:
            print(f"\n[SUCCESS] Flashing rfTestV6 completed successfully!")
            return True
        else:
            print(f"\n[ERROR] PlatformIO compilation/upload failed with code: {process.returncode}")
            return False
    except Exception as e:
        print(f"\n[ERROR] Failed to run PlatformIO command: {e}")
        return False


def start_transmitter():
    """Generates UUID, sets it on the transmitter, initiates a test session, and logs sent packets."""
    global DEFAULT_PORT
    if not DEFAULT_PORT:
        DEFAULT_PORT = select_port()
        if not DEFAULT_PORT:
            print("[ERROR] No serial port selected.")
            return
            
    print(f"\n[INFO] Connecting to Transmitter on {DEFAULT_PORT}...")
    try:
        ser = serial.Serial(DEFAULT_PORT, 115200, timeout=1.0)
    except Exception as e:
        print(f"[ERROR] Failed to connect to serial port {DEFAULT_PORT}: {e}")
        return
        
    time.sleep(2)  # Wait for ESP32 reset after serial connection
    
    # Read boot log lines
    while ser.in_waiting:
        print(f"[DEVICE] {ser.readline().decode('utf-8', errors='ignore').strip()}")
        
    while True:
        # Generate test UUID
        test_uuid = str(uuid.uuid4())
        print(f"\n[INFO] Generated UUID for this session: {test_uuid}")
        
        # Send UUID setting command
        uuid_cmd = f"u {test_uuid}\n"
        ser.write(uuid_cmd.encode('utf-8'))
        time.sleep(0.3)
        
        # Display acknowledgment
        while ser.in_waiting:
            print(f"[DEVICE] {ser.readline().decode('utf-8', errors='ignore').strip()}")
            
        print("\n--- Select Test Mode ---")
        print("  1) Formal Test (SF6 - SF12, automatic safe interval, limits 100 packets)")
        print("  2) Stress Test (Custom SF and Custom Interval, limits 100 packets)")
        print("  3) Pre-Test (Environment test, SF7, Interval 1s, runs indefinitely)")
        print("  4) Stop Transmission (Send 'x')")
        print("  5) Return to Main Menu")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '5':
            print("\n[INFO] Returning to Main Menu...")
            break
            
        if choice == '1':
            sf = input("Enter Spreading Factor (6-12) [default 7]: ").strip()
            if not sf: sf = "7"
            cmd = f"{sf}\n"
            print(f"[INFO] Starting Formal Test (SF{sf})...")
        elif choice == '2':
            sf = input("Enter Spreading Factor (6-12) [default 7]: ").strip()
            if not sf: sf = "7"
            interval = input("Enter transmission interval in ms [default 150]: ").strip()
            if not interval: interval = "150"
            cmd = f"s {sf} {interval}\n"
            print(f"[INFO] Starting Stress Test (SF{sf}, {interval}ms)...")
        elif choice == '3':
            sf = input("Enter Spreading Factor (6-12) [default 7]: ").strip()
            if not sf: sf = "7"
            cmd = f"p {sf}\n"
            print(f"[INFO] Starting Pre-Test environment scans (SF{sf})...")
        elif choice == '4':
            cmd = "x\n"
            print("[INFO] Stopping transmitter...")
        else:
            print("[ERROR] Invalid choice. Please try again.")
            continue
            
        freq = "UNKNOWN"
        if choice in ['1', '2', '3']:
            freq_input = input("Enter Frequency (433/915) for log filename: ").strip()
            if freq_input: freq = freq_input
    
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        log_path = f"logs/sent_packets_{freq}MHz_SF{sf}_{test_uuid}.csv" if choice in ['1', '2', '3'] else f"logs/sent_packets_{test_uuid}.csv"
        
        # Start transmission
        ser.write(cmd.encode('utf-8'))
        time.sleep(0.1)
        
        if choice in ['1', '2', '3']:
            print(f"\n[INFO] Logging sent packets to: {log_path}")
            print("[INFO] 您可以在此直接輸入 'x' 停止發射，或按 Ctrl+C 中斷目前測試並回到測試選單。")
            print(f"\n{'Time':<8} | {'Mode':<8} | {'SF':<4} | {'ID':<5} | {'UUID':<36} | {'Len':<5} | {'ToA':<6}")
            print("-" * 85)
            
            import sys
            import threading
            
            def keyboard_listener():
                while True:
                    try:
                        kbd_cmd = sys.stdin.readline().strip()
                        if kbd_cmd:
                            ser.write((kbd_cmd + '\n').encode('utf-8'))
                    except Exception:
                        break

            input_thread = threading.Thread(target=keyboard_listener, daemon=True)
            input_thread.start()
            
            try:
                with open(log_path, 'w', newline='', encoding='utf-8') as f:
                    csv_writer = csv.writer(f)
                    csv_writer.writerow(["Timestamp", "Mode", "SF", "PacketID", "UUID", "Length", "ToA_ms"])
                    
                    while True:
                        # 檢查 Serial 資料
                        if ser.in_waiting:
                            line = ser.readline().decode('utf-8', errors='ignore').strip()
                            if not line:
                                continue
                                
                            # Check for completion indicator
                            if "測試任務完成" in line or "回到待機" in line:
                                print(f"\n[STATUS] {line}\n")
                                break
                                
                            # Parse output format:
                            # [FORM] SF7 | ID:12 | UUID:550e8400-e29b-41d4-a716-446655440000 | Len:256 | ToA:480ms
                            match = re.search(r"\[(\w+)\]\s+SF(\d+)\s+\|\s+ID:(\d+)\s+\|\s+UUID:([\w-]+|N/A)\s+\|\s+Len:(\d+)\s+\|\s+ToA:(\d+)ms", line)
                            if match:
                                mode = match.group(1)
                                sf = match.group(2)
                                pkt_id = match.group(3)
                                uuid_str = match.group(4)
                                length = match.group(5)
                                toa = match.group(6)
                                
                                time_now = datetime.datetime.now().strftime("%H:%M:%S")
                                iso_time = datetime.datetime.now().isoformat()
                                
                                # Write row to CSV
                                csv_writer.writerow([iso_time, mode, sf, pkt_id, uuid_str, length, toa])
                                f.flush()
                                
                                # Output row
                                print(f"{time_now:<8} | {mode:<8} | SF{sf:<2} | {pkt_id:<5} | {uuid_str:<36} | {length:<5} | {toa}ms")
                            else:
                                if len(line.strip()) > 0:
                                    print(f"[RAW OUTPUT] {line}")
                        else:
                            time.sleep(0.01) # 避免 CPU 100%
                                    
            except KeyboardInterrupt:
                print("\n[INFO] 中斷目前測試。自動傳送 'x' 指令以確保發射端晶片停止廣播...")
                try:
                    ser.write(b"x\n")
                    time.sleep(0.1)
                except:
                    pass
                print("[INFO] 回到測試選單...")
                
        else:
            # Just show responses for stop command
            while ser.in_waiting:
                print(f"[DEVICE] {ser.readline().decode('utf-8', errors='ignore').strip()}")
                
    ser.close()
    print("[INFO] Connection closed.")


def run_receiver_logger():
    """Logs parsed packet data from receiver Serial port to CSV, displaying a dashboard."""
    global DEFAULT_PORT
    if not DEFAULT_PORT:
        DEFAULT_PORT = select_port()
        if not DEFAULT_PORT:
            print("[ERROR] No serial port selected.")
            return
            
    print(f"\n[INFO] Listening for incoming LoRa packets on {DEFAULT_PORT}...")
    
    freq_input = input("Enter current Frequency (433/915) for log filename: ").strip()
    freq = freq_input if freq_input else "UNKNOWN"
    
    sf_input = input("Enter current Spreading Factor (6-12) for log filename: ").strip()
    sf = sf_input if sf_input else "UNKNOWN"
    
    print("[INFO] Saving data to CSV log file. Press Ctrl+C to terminate.")
    print("[INFO] 您可以在此終端機輸入指令（如 'r' 重置統計、'6'-'12' 切換 SF）並按下 Enter 送出。")
    
    try:
        ser = serial.Serial(DEFAULT_PORT, 115200, timeout=1.0)
    except Exception as e:
        print(f"[ERROR] Failed to connect to serial port {DEFAULT_PORT}: {e}")
        return
        
    time.sleep(2) # Wait for ESP32 reset after serial connection
    if sf.isdigit() and 6 <= int(sf) <= 12:
        print(f"[INFO] Automatically switching Receiver to SF{sf}...")
        ser.write((sf + '\n').encode('utf-8'))
        time.sleep(0.5)
        
    # 建立背景執行緒監聽鍵盤輸入，並轉發給接收端 ESP32
    import threading
    def keyboard_listener():
        while True:
            try:
                cmd = input().strip()
                if cmd:
                    ser.write((cmd + '\n').encode('utf-8'))
            except (KeyboardInterrupt, EOFError, Exception):
                break

    input_thread = threading.Thread(target=keyboard_listener, daemon=True)
    input_thread.start()
        
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    print(f"\n{'Time':<8} | {'Mode':<8} | {'ID':<5} | {'UUID':<36} | {'SNR':<5} | {'RSSI':<5} | {'Loss':<5}")
    print("-" * 85)
    
    # Dictionary to keep session statistics keyed by UUID:
    # { uuid_str: {"received_ids": set, "max_id": int} }
    session_stats = {}
    
    current_uuid = None
    f = None
    csv_writer = None
    
    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue
                
            # Handle reset command notifications from receiver
            if "RESET" in line:
                print("\n[STATUS] 接收端統計數據已手動重置。\n")
                session_stats.clear()
                continue
                
            if "同步至" in line:
                print(f"\n[STATUS] {line}\n")
                continue
            
            # Parse output format from simplified receiver:
            # +RCV:<data> | SNR:<snr> | RSSI:<rssi>
            if line.startswith("+RCV:"):
                parts = line.split(" | ")
                rcv_part = parts[0]
                snr = "N/A"
                rssi = "N/A"
                
                for p in parts[1:]:
                    if p.startswith("SNR:"):
                        snr = p.split(":")[1].strip()
                    elif p.startswith("RSSI:"):
                        rssi = p.split(":")[1].strip()
                        
                payload = rcv_part[5:]  # Remove "+RCV:"
                
                # Parse payload: TST:<ID>:<UUID>***, FRM:<ID>:<UUID>***, STR:<ID>:<UUID>***
                # Or legacy: FRM:<ID>***
                if payload.startswith("TST:") or payload.startswith("FRM:") or payload.startswith("STR:"):
                    tag_map = {"TST": "PRE-TEST", "FRM": "FORM", "STR": "STRESS"}
                    mode_tag = tag_map.get(payload[:3], "UNKNOWN")
                    
                    first_colon = payload.find(':')
                    second_colon = payload.find(':', first_colon + 1)
                    asterisk = payload.find('*')
                    if asterisk == -1:
                        asterisk = len(payload)
                        
                    id_str = ""
                    uuid_str = "N/A"
                    
                    if second_colon != -1 and second_colon < asterisk:
                        id_str = payload[first_colon + 1:second_colon]
                        uuid_str = payload[second_colon + 1:asterisk]
                    else:
                        id_str = payload[first_colon + 1:asterisk]
                        
                    try:
                        pkt_id = int(id_str)
                    except ValueError:
                        if len(line.strip()) > 0:
                            print(f"[RAW OUTPUT] {line}")
                        continue
                        
                    # Python-side Packet Loss Rate Calculation (isolated per UUID)
                    if uuid_str not in session_stats:
                        session_stats[uuid_str] = {
                            "received_ids": set(),
                            "max_id": -1
                        }
                    
                    stats = session_stats[uuid_str]
                    
                    # Detect sender reset (ID goes back to 0, or drops significantly below max_id)
                    if pkt_id < stats["max_id"] - 5 or (pkt_id == 0 and stats["max_id"] > 0):
                        print(f"\n[STATUS] 偵測到 UUID {uuid_str} 的發射端重置，重置該會話統計數據。\n")
                        stats["received_ids"].clear()
                        stats["max_id"] = -1
                        
                    stats["received_ids"].add(pkt_id)
                    
                    if pkt_id > stats["max_id"]:
                        stats["max_id"] = pkt_id
                        
                    total_expected = stats["max_id"] + 1
                    received_count = len(stats["received_ids"])
                    lost_count = total_expected - received_count
                    loss = (lost_count / total_expected * 100.0) if total_expected > 0 else 0.0
                    
                    # Dynamically open/switch CSV file based on received UUID
                    if uuid_str != current_uuid:
                        if f:
                            f.close()
                        current_uuid = uuid_str
                        log_path = f"logs/received_packets_{freq}MHz_SF{sf}_{current_uuid}.csv"
                        file_exists = os.path.exists(log_path)
                        f = open(log_path, 'a', newline='', encoding='utf-8')
                        csv_writer = csv.writer(f)
                        if not file_exists:
                            csv_writer.writerow(["Timestamp", "Mode", "PacketID", "UUID", "SNR_dB", "RSSI_dBm", "LossRate"])
                            f.flush()
                        print(f"\n[INFO] Active session changed to UUID: {current_uuid}. Logging to: {log_path}\n")
                    
                    time_now = datetime.datetime.now().strftime("%H:%M:%S")
                    iso_time = datetime.datetime.now().isoformat()
                    
                    # Save formal and stress tests to CSV
                    if mode_tag in ["FORM", "STRESS"] and csv_writer:
                        csv_writer.writerow([iso_time, mode_tag, pkt_id, uuid_str, snr, rssi, f"{loss:.2f}"])
                        f.flush()
                        
                    # Display table row
                    print(f"{time_now:<8} | {mode_tag:<8} | {pkt_id:<5} | {uuid_str:<36} | {snr:<5} | {rssi:<5} | {loss:.2f}%")
            elif "+RCV_ERR: CRC Error!" in line:
                time_now = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"{time_now:<8} | [WARNING] CRC Error detected! (Packet corrupted)")
                if f and csv_writer and current_uuid:
                    iso_time = datetime.datetime.now().isoformat()
                    csv_writer.writerow([iso_time, "CRC_ERR", "N/A", current_uuid, "N/A", "N/A", "N/A"])
                    f.flush()
            else:
                if len(line.strip()) > 0:
                    print(f"[RAW OUTPUT] {line}")
                    
    except KeyboardInterrupt:
        print("\n\n[INFO] Data logging terminated by user.")
        raise KeyboardInterrupt
    finally:
        if f:
            f.close()
        ser.close()

def analyze_log():
    """Lists CSV logs and analyzes the packet loss rate for the selected log."""
    if not os.path.exists('logs'):
        print("\n[ERROR] No logs directory found.")
        return
        
    csv_files = [f for f in os.listdir('logs') if f.endswith('.csv')]
    if not csv_files:
        print("\n[ERROR] No CSV logs found in the logs/ directory.")
        return
        
    print("\n=== Available Log Files ===")
    for idx, filename in enumerate(csv_files, start=1):
        print(f"  {idx}) {filename}")
        
    choice = input(f"\nSelect a log file to analyze (1-{len(csv_files)}): ").strip()
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(csv_files)):
            raise ValueError
        selected_file = csv_files[idx]
    except ValueError:
        print("[ERROR] Invalid selection.")
        return
        
    filepath = os.path.join('logs', selected_file)
    print(f"\n[INFO] Analyzing {selected_file}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            packet_ids = set()
            snr_list = []
            rssi_list = []
            crc_errors = 0
            
            for row in reader:
                if row.get('Mode') == 'CRC_ERR':
                    crc_errors += 1
                    continue
                    
                if 'PacketID' in row:
                    try:
                        packet_ids.add(int(row['PacketID']))
                    except ValueError:
                        pass
                if 'SNR_dB' in row and row['SNR_dB'] != 'N/A':
                    try: snr_list.append(float(row['SNR_dB']))
                    except: pass
                if 'RSSI_dBm' in row and row['RSSI_dBm'] != 'N/A':
                    try: rssi_list.append(float(row['RSSI_dBm']))
                    except: pass
                    
            if not packet_ids:
                print("[WARNING] No valid Packet IDs found in the log.")
                return
                
            auto_max_id = max(packet_ids)
            print(f"\n[INFO] Auto-detected max Packet ID: {auto_max_id} (Expected total: {auto_max_id + 1})")
            custom_max = input(f"Enter custom max Packet ID (or press Enter to keep {auto_max_id}): ").strip()
            
            if custom_max and custom_max.isdigit():
                max_id = int(custom_max)
                if max_id < auto_max_id:
                    print(f"[WARNING] Custom max ID ({max_id}) is less than actually received max ID ({auto_max_id}). Using {auto_max_id} instead.")
                    max_id = auto_max_id
            else:
                max_id = auto_max_id
                
            total_expected = max_id + 1
            total_received = len(packet_ids)
            lost_count = total_expected - total_received
            completely_missed = lost_count - crc_errors if lost_count >= crc_errors else 0
            loss_rate = (lost_count / total_expected) * 100.0 if total_expected > 0 else 0
            
            avg_snr = sum(snr_list) / len(snr_list) if snr_list else 0
            avg_rssi = sum(rssi_list) / len(rssi_list) if rssi_list else 0
            
            print("\n" + "=" * 40)
            print("          ANALYSIS REPORT")
            print("=" * 40)
            print(f"  Total Expected Packets : {total_expected}")
            print(f"  Valid Received Packets : {total_received}")
            print(f"  CRC Error Packets      : {crc_errors}")
            print(f"  Completely Missed      : {completely_missed}")
            print(f"  Total Lost Packets     : {lost_count}")
            print(f"  Packet Loss Rate       : {loss_rate:.2f} %")
            print("-" * 40)
            print(f"  Average SNR            : {avg_snr:.2f} dB")
            print(f"  Average RSSI           : {avg_rssi:.2f} dBm")
            print("=" * 40 + "\n")
            
    except Exception as e:
        print(f"[ERROR] Failed to read or parse CSV: {e}")

def main():
    """Main execution menu loop."""
    while True:
        print("\n" + "=" * 64)
        print("          LoRa Avionic Link Test & Flashing Manager             ")
        print("=" * 64)
        print("  1) Scan and Select Serial Port")
        print("  2) Flash Firmware (Configure Carrier Freq, Compile & Upload)")
        print("  3) Start Transmitter (Generate UUID & Initiate Test Session)")
        print("  4) Run Receiver Data Logger (Listen & Log to CSV)")
        print("  5) Analyze Packet Loss from Log")
        print("  6) Exit")
        print("=" * 64)
        
        if DEFAULT_PORT:
            print(f"[Current Port: {DEFAULT_PORT}]")
        else:
            print("[Current Port: None - Select option 1 to search]")
            
        try:
            choice = input("\nEnter option (1-5): ").strip()
            
            if choice == '1':
                select_port()
            elif choice == '2':
                flash_firmware()
            elif choice == '3':
                start_transmitter()
            elif choice == '4':
                run_receiver_logger()
            elif choice == '5':
                analyze_log()
            elif choice == '6':
                print("\nExiting. Thank you!")
                break
            else:
                print("[ERROR] Invalid choice. Please select again.")
                
            input("\nPress Enter to return to menu...")
        except KeyboardInterrupt:
            print("\n[INFO] 偵測到取消動作，回到主選單...")


if __name__ == "__main__":
    main()
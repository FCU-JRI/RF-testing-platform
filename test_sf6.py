import serial
import time
import threading

def read_port(ser, name):
    while getattr(threading.current_thread(), "do_run", True):
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"[{name}] {line}")
        time.sleep(0.01)

def main():
    print("Opening ports...")
    sender = serial.Serial('/dev/cu.usbserial-310', 115200, timeout=1)
    receiver = serial.Serial('/dev/cu.usbserial-1110', 115200, timeout=1)

    t1 = threading.Thread(target=read_port, args=(sender, "SENDER"))
    t2 = threading.Thread(target=read_port, args=(receiver, "RECEIVER"))
    t1.start()
    t2.start()

    time.sleep(2)
    print("\n--- Sending commands ---")
    
    # Set Length to 255
    print("Setting length to 255...")
    receiver.write(b"l 255\n")
    sender.write(b"l 255\n")
    time.sleep(1)

    # Send SF6 command to Receiver
    print("Setting Receiver to SF6...")
    receiver.write(b"6\n")
    time.sleep(1)

    # Send SF6 command to Sender
    print("Setting Sender to SF6...")
    sender.write(b"6\n")
    
    # Let it run for 10 seconds
    time.sleep(10)
    
    # Stop threads
    t1.do_run = False
    t2.do_run = False
    t1.join()
    t2.join()
    
    sender.close()
    receiver.close()
    print("Done testing.")

if __name__ == '__main__':
    main()

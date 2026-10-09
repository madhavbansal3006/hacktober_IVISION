#!/usr/bin/env python3
"""
Serial/USB to Shiggaon Watershed Intelligence API Gateway Bridge.
Reads telemetry JSON over USB Serial from Arduino / ESP32 / Raspberry Pi
and posts it to the FastAPI backend.
"""

import sys
import time
import json
import requests
import argparse

DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1/telemetry"

def main():
    parser = argparse.ArgumentParser(description="Bridge Serial IoT readings to Shiggaon API")
    parser.add_argument("--port", type=str, default="/dev/tty.usbmodem14101", help="Serial port (e.g. /dev/ttyUSB0, COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default 115200)")
    parser.add_argument("--api", type=str, default=DEFAULT_API_URL, help="Target API endpoint")
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("Pyserial is required for USB serial reading. Install with: pip install pyserial")
        sys.exit(1)

    print(f"Connecting to Serial Port {args.port} at {args.baud} baud...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=2)
        time.sleep(2)
        print("Connected! Listening for sensor telemetry packets...")
    except Exception as e:
        print(f"Error opening serial port {args.port}: {e}")
        sys.exit(1)

    while True:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            print(f"Serial Raw: {line}")
            if line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                response = requests.post(args.api, json=data, timeout=5)
                if response.status_code == 200:
                    res_data = response.json()
                    print(f"✓ Ingested to API | MWS: {res_data.get('MWS')} | Live Risk: {res_data.get('live_risk_score')} ({res_data.get('live_risk_category')})")
                else:
                    print(f"✗ API Error {response.status_code}: {response.text}")
        except KeyboardInterrupt:
            print("\nExiting IoT Serial Bridge.")
            break
        except Exception as e:
            print(f"Bridge error: {e}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Continuous USB Serial to Shiggaon API Live Streamer.
Reads raw terminal output from the ESP32 via USB Serial using pySerial,
parses real hardware sensor values (Check-Dam Capacity, Precipitation Gauge,
Soil Saturation, Siltation NTU) and automatically pushes live telemetry to the
Shiggaon Watershed Intelligence API in real time.
"""

import re
import time
from datetime import datetime
import json
import os
import urllib.request
import urllib.error
import serial

SERIAL_PORT = "/dev/cu.usbserial-0001"
BAUD_RATE = 115200
API_URL = os.environ.get("SHIGGAON_API_URL", "http://127.0.0.1:8000/api/v1/telemetry")

def post_telemetry(payload):
    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            API_URL,
            data=data_bytes,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                return result
    except Exception as e:
        print(f"API post error: {e}", flush=True)
        return None
    return None

import os
import subprocess

def free_serial_port(port):
    try:
        subprocess.run(["pkill", "-9", "-f", "serial-monitor"], stderr=subprocess.DEVNULL)
        out = subprocess.check_output(["lsof", port], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                pid = int(parts[1])
                print(f"🔧 Automatically releasing locked port from {parts[0]} (PID {pid})...", flush=True)
                os.kill(pid, 9)
                time.sleep(0.5)
    except Exception:
        pass

def stream():
    free_serial_port(SERIAL_PORT)
    print(f"Connecting to ESP32 on {SERIAL_PORT} at {BAUD_RATE} baud...", flush=True)
    try:
        ser = serial.Serial()
        ser.port = SERIAL_PORT
        ser.baudrate = BAUD_RATE
        ser.timeout = 1
        ser.dtr = False
        ser.rts = False
        ser.open()
        # Pulse reset with DTR=False to guarantee SPI_FAST_FLASH_BOOT
        ser.dtr = False
        ser.rts = True
        time.sleep(0.1)
        ser.rts = False
        time.sleep(0.5)
        print("✓ Connected to ESP32! Listening for physical sensor stream...", flush=True)
    except Exception as e:
        print(f"⚠️ Could not open {SERIAL_PORT}: {e}", flush=True)
        print("Make sure the Serial Monitor in Arduino IDE is closed.", flush=True)
        return

    current_data = {
        "device_id": "ESP32_SHIGGAON_NODE_01",
        "mws_code": "4D4F2m3",
        "id": "g_mws.240575",
        "rainfall_mm_hr": 0.0,
        "rainfall_mm": 0.0,
        "soil_moisture_pct": 67.8,
        "water_level_cm": 5.8,
        "turbidity_ntu": 0.0,
        "ph": 7.5,
        "air_temperature_c": 28.0,
        "humidity_pct": 65.0,
        "water_temperature_c": 26.0
    }

    initial_rainfall_offset = None
    last_sent = 0

    # Send initial reset so dashboard reflects 0.0 mm immediately
    print("🔄 Resetting rainfall session to 0.0 mm on dashboard...", flush=True)
    post_telemetry(current_data)

    while True:
        try:
            raw_bytes = ser.readline()
            if not raw_bytes:
                continue
            line = raw_bytes.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # Echo raw line from ESP32 so the user can verify
            print(f"[ESP32] {line}", flush=True)

            # 1. If JSON is printed
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    if "rainfall_mm" in data:
                        parsed_r = float(data["rainfall_mm"])
                        if initial_rainfall_offset is None:
                            initial_rainfall_offset = parsed_r
                            print(f"🔄 Rainfall calibrated to 0.0 mm (baseline offset: {initial_rainfall_offset:.2f} mm)", flush=True)
                        data["rainfall_mm"] = round(max(0.0, parsed_r - initial_rainfall_offset), 2)
                    res = post_telemetry(data)
                    if res:
                        print(f"🔥 LIVE UPDATE -> Risk={res.get('live_risk_score')} ({res.get('compound_alert_level')})", flush=True)
                    continue
                except Exception:
                    pass

            # 2. Parse formatted terminal lines
            # Check-Dam Capacity   : 5.8 cm
            m_dam = re.search(r"Check-Dam Capacity\s*:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_dam:
                current_data["water_level_cm"] = float(m_dam.group(1))

            # Precipitation Gauge  : 38.61 mm (CUMULATIVE)
            m_rain = re.search(r"Precipitation Gauge\s*:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_rain:
                parsed_rain = float(m_rain.group(1))
                if initial_rainfall_offset is None:
                    initial_rainfall_offset = parsed_rain
                    print(f"🔄 Rainfall session calibrated to 0.0 mm (zero-offset: {initial_rainfall_offset:.2f} mm)", flush=True)
                current_data["rainfall_mm"] = round(max(0.0, parsed_rain - initial_rainfall_offset), 2)
                current_data["rainfall_mm_hr"] = current_data["rainfall_mm"]
                print(f"🌧️  SESSION RAINFALL: {current_data['rainfall_mm']} mm (Raw ESP32: {parsed_rain} mm)", flush=True)

            # Soil Saturation Index: 67.8 % VWC
            m_soil = re.search(r"Soil Saturation Index\s*:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_soil:
                current_data["soil_moisture_pct"] = float(m_soil.group(1))

            # Topsoil Siltation NTU: 0.0 NTU
            m_turb = re.search(r"Topsoil Siltation.*?:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_turb:
                current_data["turbidity_ntu"] = float(m_turb.group(1))

            # Runoff Stream Acidity: 7.57 pH
            m_ph = re.search(r"Runoff Stream Acidity\s*:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_ph:
                current_data["ph"] = float(m_ph.group(1))

            # Canopy Air Temp      : 28.3 °C
            m_temp = re.search(r"Canopy Air Temp\s*:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_temp:
                current_data["air_temperature_c"] = float(m_temp.group(1))
                # If water sensor reading not available, use ambient calibrated water temp
                current_data["water_temperature_c"] = round(float(m_temp.group(1)) - 1.5, 1)

            # Canopy Air Humidity  : 65.0 %
            m_hum = re.search(r"Canopy Air Humidity\s*:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_hum:
                current_data["humidity_pct"] = float(m_hum.group(1))

            # Reservoir Fluid Temp / Liquid Layer: 26.8 °C (if not error)
            m_wtemp = re.search(r"Reservoir (?:Fluid|Liquid).*?:\s*([0-9\.]+)", line, re.IGNORECASE)
            if m_wtemp:
                current_data["water_temperature_c"] = float(m_wtemp.group(1))

            now = time.time()
            # Send to API every 2 seconds
            if now - last_sent >= 2.0:
                last_sent = now
                current_data["timestamp"] = datetime.now().isoformat()
                current_data["rainfall_mm_hr"] = current_data.get("rainfall_mm", 0.0)
                res = post_telemetry(current_data)
                if res:
                    print(f"⚡ LIVE SYNC: Rain={current_data['rainfall_mm']}mm | Soil={current_data['soil_moisture_pct']}% | Level={current_data['water_level_cm']}cm | NTU={current_data['turbidity_ntu']} | pH={current_data['ph']} | Temp={current_data['water_temperature_c']}°C => Live Risk: {res.get('live_risk_score')} ({res.get('compound_alert_level')})", flush=True)

        except KeyboardInterrupt:
            print("\nExiting Live Streamer.", flush=True)
            break
        except Exception as e:
            time.sleep(0.2)

if __name__ == "__main__":
    stream()

#!/usr/bin/env python3
"""
MH-Z19B CO₂ Sensor Reader  (Raspberry Pi 5)
UART : /dev/serial0  (TxD=GPIO14, RxD=GPIO15)
"""

import time
import serial
from datetime import datetime

SERIAL_PORT = "/dev/serial0"
BAUD = 9600
INTERVAL_S = 5
CMD_GET_PPM = bytearray([0xFF, 0x01, 0x86,
                         0x00, 0x00, 0x00, 0x00, 0x00,
                         0x79])

last_valid_result = None


def read_mhz19(ser):
    """
    센서로부터 9바이트 프레임을 읽고 유효한지 검사
    """
    ser.reset_input_buffer()
    ser.write(CMD_GET_PPM)
    resp = ser.read(9)

    if len(resp) != 9 or resp[0] != 0xFF or resp[1] != 0x86:
        return None

    co2 = resp[2] * 256 + resp[3]
    temp = resp[4] - 40
    return co2, temp, resp


def wait_for_sensor_response(ser, timeout=10):
    """
    센서가 유효한 응답을 줄 때까지 대기, 실패 시 None 반환
    """
    print("🚀  MH-Z19B reader initializing...")
    start_time = time.time()

    while True:
        result = read_mhz19(ser)
        if result:
            print("✅  Sensor ready!\n")
            return result
        if time.time() - start_time > timeout:
            print("❌  센서 응답 없음 (10초 제한 초과)")
            return None
        time.sleep(0.5)


def init():
    """
    시리얼 포트를 열고 초기 유효 응답을 기다림
    """
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    first_response = wait_for_sensor_response(ser)

    global last_valid_result
    if first_response:
        last_valid_result = first_response
    return ser


def main():
    global last_valid_result
    min_co2 = None

    try:
        ser = init()
    except Exception as e:
        print("❌ 시리얼 포트 열기 실패:", e)
        return

    while True:
        result = read_mhz19(ser)
        if result:
            last_valid_result = result
        elif last_valid_result:
            print("⚠️  최신 유효 값으로 대체 (센서 응답 없음)")
            result = last_valid_result
        else:
            print("❌  측정 실패: 유효한 센서 응답 없음 (최초)")
            time.sleep(INTERVAL_S)
            continue

        co2, temp, _ = result
        if (min_co2 is None) or (co2 < min_co2):
            min_co2 = co2

        t0 = time.perf_counter_ns()
        print("———", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "———")
        print(f"CO2: {co2} ppm")
        print(f"Min CO2: {min_co2 if min_co2 else 'N/A'} ppm")
        print(f"Temperature: {temp} °C")
        print("Accuracy:  ±50 ppm ±5 %")
        elapsed_us = (time.perf_counter_ns() - t0) // 1_000
        print(f"⏱ Print-block time: {elapsed_us} µs\n")

        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 종료합니다.")

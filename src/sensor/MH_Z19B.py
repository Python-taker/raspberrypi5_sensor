#!/usr/bin/env python3
"""
ZH_19B.py
────────────────────────────────────────────────────────
- MH-Z19B CO₂ 센서를 Raspberry Pi 5의 UART(/dev/serial0)로 제어/측정
- 초기화 시 센서 유효 응답 대기 → 주기 측정(5s) → CO₂, 온도, 최소 CO₂ 출력
- 센서 응답 없음 시 마지막 유효값 재사용

!! 주의 사항 !!
1) UART 활성화 필요 (raspi-config → Interface Options → Serial Port)
   - 콘솔 사용 비활성화, 하드웨어 UART만 활성화
2) MH-Z19B 전원: 5V, GND 공통
3) 데이터시트 명령 0x86(GET PPM) 사용, 9바이트 프레임 수신
4) 센서 응답 지연 시 첫 10초까지 재시도

📌 사용법
- 단독 실행(테스트): `python3 ZH_19B.py` (로그 출력)
- 외부 import: `init()`, `read_mhz19()` 호출 (기본은 조용히 동작)
"""

import time
import serial
from datetime import datetime
from typing import Optional, Tuple

SERIAL_PORT = "/dev/serial0"
BAUD = 9600
INTERVAL_S = 5
CMD_GET_PPM = bytearray([0xFF, 0x01, 0x86,
                         0x00, 0x00, 0x00, 0x00, 0x00,
                         0x79])

last_valid_result: Optional[Tuple[int, int, bytes]] = None

# =====================================================
# 1️⃣ CO₂ 데이터 프레임 읽기
# =====================================================
def read_mhz19(ser: serial.Serial) -> Optional[Tuple[int, int, bytes]]:
    """
    MH-Z19B 센서에서 CO₂, 온도 데이터를 읽어 반환.

    Args:
        ser (serial.Serial): 열린 시리얼 포트 객체

    Returns:
        tuple[int, int, bytes] | None:
            (CO₂[ppm], 온도[°C], 원시프레임[bytes]) / 유효하지 않으면 None
    """
    ser.reset_input_buffer()
    ser.write(CMD_GET_PPM)
    resp = ser.read(9)

    if len(resp) != 9 or resp[0] != 0xFF or resp[1] != 0x86:
        return None

    co2 = resp[2] * 256 + resp[3]
    temp = resp[4] - 40
    return co2, temp, resp

# =====================================================
# 2️⃣ 센서 응답 대기
# =====================================================
def wait_for_sensor_response(ser: serial.Serial, timeout: int = 10, *, verbose: bool = False)\
        -> Optional[Tuple[int, int, bytes]]:
    """
    MH-Z19B 센서 유효 응답 대기.

    Args:
        ser (serial.Serial): 열린 시리얼 포트
        timeout (int): 최대 대기 시간(초)
        verbose (bool): True면 상태 로그 출력

    Returns:
        tuple[int, int, bytes] | None: 첫 유효 응답, 실패 시 None
    """
    if verbose:
        print("🚀  MH-Z19B reader initializing...")
    start_time = time.time()

    while True:
        result = read_mhz19(ser)
        if result:
            if verbose:
                print("✅  Sensor ready!\n")
            return result
        if time.time() - start_time > timeout:
            if verbose:
                print("❌  센서 응답 없음 (10초 제한 초과)")
            return None
        time.sleep(0.5)

# =====================================================
# 3️⃣ 센서 초기화
# =====================================================
def init(*, verbose: bool = False) -> serial.Serial:
    """
    MH-Z19B 센서 초기화(시리얼 오픈 + 첫 유효 응답 대기).

    Args:
        verbose (bool): True면 초기화 로그 출력

    Returns:
        serial.Serial: 열린 시리얼 포트 객체
    """
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    first_response = wait_for_sensor_response(ser, timeout=10, verbose=verbose)

    global last_valid_result
    if first_response:
        last_valid_result = first_response
    return ser

# =====================================================
# 4️⃣ 단독 테스트용 메인 루프 (import 시 실행되지 않음)
# =====================================================
def main():
    """
    MH-Z19B CO₂ 센서 측정 루프(테스트용, 로그 출력 포함).
    """
    global last_valid_result
    min_co2 = None

    try:
        ser = init(verbose=True)
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

# =====================================================
# 5️⃣ 단독 실행 진입점
# =====================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 종료합니다.")

# ─────────────────────────────────────────────────────
# 함수 인벤토리 (요약 표)
# ─────────────────────────────────────────────────────
# 함수명                    | 기능 설명
# ------------------------- | -----------------------------------------------
# read_mhz19               | 센서에 명령 전송 후 CO₂/온도/프레임 수신
# wait_for_sensor_response | 첫 유효 응답이 올 때까지 대기(무음 기본)
# init                     | 시리얼 포트 열고 초기 유효 응답 대기(무음 기본)
# main                     | 테스트용 주기 측정 루프(로그 출력)
#
# 입력값(파라미터 타입)
# - read_mhz19(ser: serial.Serial)
# - wait_for_sensor_response(ser: serial.Serial, timeout: int=10, verbose: bool=False)
# - init(verbose: bool=False)
# - main()
#
# 반환값
# - read_mhz19(): tuple[int, int, bytes] | None
# - wait_for_sensor_response(): tuple[int, int, bytes] | None
# - init(): serial.Serial
# - main(): None
#
# 주의사항/로직 요약
# - UART 활성화 필수
# - 초기 무응답 시 10초 후 None 반환(메인에서 처리)
# - 데이터시트 CRC 미검증(필요 시 확장 가능)

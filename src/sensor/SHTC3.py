#!/usr/bin/env python3
"""
SHTC3.py
────────────────────────────────────────────────────────
- PCA9548A I²C 멀티플렉서(주소 0x74) 채널 2~5에 연결된 SHTC3 센서 4개의 온습도 측정
- 각 채널 순차 전환 → 센서 Wake → ID CRC 검증 → 측정 → Sleep 순으로 동작

!! 주의 사항 !!
1) I²C 활성화 필요 (raspi-config → Interface Options → I2C → Enable)
2) PCA9548A 주소, SHTC3 주소 고정(0x70)
3) CRC 오류 발생 시 데이터 무효 처리
4) 각 센서 간 짧은 대기 시간 필요 (0.05~0.2초)

📌 호출 관계 및 사용법
- 단독 실행 가능 (CLI 테스트용): `python3 SHTC3.py`
- 다른 모듈에서 import 시: `select_channel()`, `read_single_sensor()` 등 개별 함수 호출 가능
"""

import time
from smbus2 import SMBus, i2c_msg
from typing import List, Tuple

# ─── 주소 정의 ─────────────────────────────
PCA9548A_ADDR = 0x74        # 멀티플렉서 주소
SHTC3_ADDR    = 0x70        # SHTC3 고정 주소
TARGET_CHANNELS = [2, 3, 4, 5]   # 읽고 싶은 채널들

# ─── 로그 제어 ─────────────────────────────
VERBOSE = False  # True로 하면 디버그 출력(🆔 ID raw 등) 표시

# =====================================================
# 1️⃣ CRC-8 (Sensirion) 계산
# 다항식 0x31, 초기값 0xFF
# =====================================================
def crc8(data: List[int]) -> int:
    """
    Sensirion CRC-8 계산 (SHTC3/SHT4x 시리즈용).

    Args:
        data: CRC 계산 대상 바이트 리스트

    Returns:
        계산된 CRC 값 (0~255)
    """
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31)
            else:
                crc <<= 1
            crc &= 0xFF
    return crc

# =====================================================
# 2️⃣ PCA9548A 채널 선택
# =====================================================
def select_channel(bus: SMBus, ch: int) -> None:
    """
    PCA9548A에서 특정 채널을 선택.

    Args:
        bus: I²C 버스 객체
        ch: 활성화할 채널 번호 (0~7)
    """
    bus.write_byte(PCA9548A_ADDR, 1 << ch)
    time.sleep(0.05)

# =====================================================
# 3️⃣ 센서 Wake/Sleep/Reset 명령
# =====================================================
def wake_sensor(bus: SMBus) -> None:
    """SHTC3 센서를 Wake 상태로 전환."""
    bus.write_i2c_block_data(SHTC3_ADDR, 0x35, [0x17])
    time.sleep(0.2)

def sleep_sensor(bus: SMBus) -> None:
    """SHTC3 센서를 Sleep 상태로 전환."""
    bus.write_i2c_block_data(SHTC3_ADDR, 0xB0, [0x98])
    time.sleep(0.01)

def reset_sensor(bus: SMBus) -> None:
    """SHTC3 센서 소프트리셋."""
    bus.write_i2c_block_data(SHTC3_ADDR, 0x80, [0x5D])
    time.sleep(0.05)

# =====================================================
# 4️⃣ Wake 후 ID 확인 (옵션)
# CRC 검증으로 센서 ID 응답 유효성 확인
# =====================================================
def verify_wake(bus: SMBus) -> bool:
    """
    SHTC3 센서 Wake 상태 확인 및 ID CRC 검증.

    Returns:
        ID 응답 길이=3, CRC 일치 시 True
    """
    try:
        bus.write_i2c_block_data(SHTC3_ADDR, 0xEF, [0xC8])
        time.sleep(0.01)
        read = i2c_msg.read(SHTC3_ADDR, 3)
        bus.i2c_rdwr(read)
        id_bytes = list(read)
        if VERBOSE:
            print(f"    🆔 ID raw: {id_bytes}")
        return len(id_bytes) == 3 and crc8(id_bytes[:2]) == id_bytes[2]
    except Exception:
        return False

# =====================================================
# 5️⃣ 온습도 측정
# 고정밀 측정 명령(0x7C, 0xA2) 사용 후 CRC 검증
# =====================================================
def measure(bus: SMBus) -> Tuple[float, float]:
    """
    SHTC3 센서에서 온도/습도 측정.

    Returns:
        (온도[°C], 습도[%RH])

    Raises:
        ValueError: CRC 검증 실패
    """
    bus.write_i2c_block_data(SHTC3_ADDR, 0x7C, [0xA2])
    time.sleep(0.2)
    read = i2c_msg.read(SHTC3_ADDR, 6)
    bus.i2c_rdwr(read)
    data = list(read)
    if crc8(data[:2]) != data[2] or crc8(data[3:5]) != data[5]:
        raise ValueError("CRC check failed")

    t_raw = (data[0] << 8) | data[1]
    h_raw = (data[3] << 8) | data[4]
    temperature = -45 + 175 * (t_raw / 65535.0)
    humidity = 100 * (h_raw / 65535.0)
    return round(temperature, 1), round(humidity, 1)

# =====================================================
# 6️⃣ 센서 1개 읽기 시퀀스
# Reset → Wake → (선택) ID 확인 → 측정 → Sleep
# =====================================================
def read_single_sensor(bus: SMBus, verify: bool = True) -> Tuple[float, float]:
    """
    SHTC3 센서 단일 측정 시퀀스.

    Args:
        verify: ID CRC 검증 수행 여부 (기본 True, 성능 필요시 False)

    Returns:
        (온도[°C], 습도[%RH])

    Raises:
        RuntimeError: Wake 실패 또는 ID CRC 불일치
    """
    reset_sensor(bus)
    wake_sensor(bus)
    if verify and not verify_wake(bus):
        raise RuntimeError("센서 wake 실패 또는 ID CRC 불일치")
    temp, hum = measure(bus)
    sleep_sensor(bus)
    return temp, hum

# =====================================================
# 7️⃣ 단독 실행 진입점 (import 시에는 실행되지 않음)
# =====================================================
if __name__ == '__main__':
    with SMBus(1) as bus:
        for ch in TARGET_CHANNELS:
            if VERBOSE:
                print(f"\n🔀 채널 {ch} 선택")
            select_channel(bus, ch)
            try:
                t, h = read_single_sensor(bus)
                if VERBOSE:
                    print(f"✅ CH{ch}: {t} °C, {h}% RH")
            except Exception as e:
                if VERBOSE:
                    print(f"❌ CH{ch} 오류: {e}")

# ─────────────────────────────────────────────────────
# 함수 인벤토리 (요약 표)
# ─────────────────────────────────────────────────────
# 함수명             | 기능 설명
# ------------------ | --------------------------------------------------------
# crc8               | Sensirion CRC-8 계산
# select_channel     | PCA9548A에서 지정 채널 활성화
# wake_sensor        | SHTC3를 Wake 상태로 전환
# sleep_sensor       | SHTC3를 Sleep 상태로 전환
# reset_sensor       | SHTC3 소프트리셋
# verify_wake        | SHTC3 ID 요청 및 CRC 검증
# measure            | 온습도 측정 및 CRC 검증
# read_single_sensor | 센서 1개 측정 시퀀스 실행

#!/usr/bin/env python3
"""
SHT41.py
────────────────────────────────────────────────────────
- PCA9548A I²C 멀티플렉서(주소 0x74) 채널 1에 연결된 SHT41 센서에서 온습도 측정
- CRC-8 검증 포함, 고정밀 측정 모드(0xFD) 사용

!! 주의 사항 !!
1) I²C 활성화 필요 (raspi-config → Interface Options → I2C → Enable)
2) PCA9548A 주소와 채널 번호(TARGET_CHANNEL) 확인 필수
3) CRC 오류 발생 시 데이터 무효 처리

📌 호출 관계 및 사용법
- 단독 실행 가능 (CLI 테스트용): `python3 SHT41.py`
- 다른 모듈에서 import 시: `select_channel()`, `read_sht41()` 사용 가능
"""

import time
from smbus2 import SMBus, i2c_msg
from typing import Tuple

# ─── 주소 정의 ─────────────────────────────
PCA9548A_ADDR  = 0x74       # PCA9548A I2C 주소
SHT41_ADDR     = 0x44       # SHT4x 센서 고정 주소
TARGET_CHANNEL = 1          # SHT41 연결 채널

# ─── 로그 제어 ─────────────────────────────
VERBOSE = False  # 단독 실행 시 True로 두면 로그가 보임

# =====================================================
# 1️⃣ PCA9548A 채널 선택
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
# 2️⃣ CRC 확인 (SHT4x CRC-8 알고리즘)
# =====================================================
def validate_crc(data_bytes, crc_value) -> bool:
    """
    SHT4x 센서 데이터 CRC-8 검증.

    Args:
        data_bytes (list[int]): CRC 계산 대상 바이트 리스트
        crc_value (int): 수신된 CRC 값
    """
    crc = 0xFF
    for byte in data_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x31
            else:
                crc <<= 1
            crc &= 0xFF
    return crc == crc_value

# =====================================================
# 3️⃣ SHT41 측정 및 변환
# =====================================================
def read_sht41(bus: SMBus) -> Tuple[float, float]:
    """
    SHT41 센서에서 온도/습도 데이터를 측정.

    Args:
        bus: I²C 버스 객체

    Returns:
        (온도[°C], 습도[%RH])

    Raises:
        RuntimeError: 수신 데이터 길이 오류
        ValueError: CRC 검증 실패
        OSError: I²C 통신 오류
    """
    # 고정밀 측정 명령 (0xFD)
    bus.write_byte(SHT41_ADDR, 0xFD)
    time.sleep(0.5)  # 데이터 준비 시간

    # 데이터 읽기 (6바이트: T[2]+CRC + RH[2]+CRC)
    read = i2c_msg.read(SHT41_ADDR, 6)
    bus.i2c_rdwr(read)
    data = list(read)

    if len(data) != 6:
        raise RuntimeError("센서 데이터 길이 오류")

    # CRC 확인
    if not validate_crc(data[:2], data[2]) or not validate_crc(data[3:5], data[5]):
        raise ValueError("CRC 오류 발생")

    t_raw = (data[0] << 8) | data[1]
    h_raw = (data[3] << 8) | data[4]

    # 데이터 변환 공식 (Datasheet 기준)
    temperature = -45 + (175 * (t_raw / 65535.0))
    humidity    = 100 * (h_raw / 65535.0)

    return round(temperature, 1), round(humidity, 1)

# =====================================================
# 4️⃣ 단독 실행 진입점 (import 시에는 실행되지 않음)
# =====================================================
if __name__ == '__main__':
    with SMBus(1) as bus:
        if VERBOSE:
            print(f"\n🔀 채널 {TARGET_CHANNEL} 선택")
        select_channel(bus, TARGET_CHANNEL)

        try:
            temp, hum = read_sht41(bus)
            if VERBOSE:
                print(f"✅ SHT41 측정 결과: {temp} °C, {hum}% RH")
        except Exception as e:
            if VERBOSE:
                print(f"❌ SHT41 오류: {e}")

# ─────────────────────────────────────────────────────
# 함수 인벤토리 (요약 표)
# ─────────────────────────────────────────────────────
# 함수명          | 기능 설명
# --------------- | ----------------------------------------------------------
# select_channel  | PCA9548A에서 지정 채널 활성화
# validate_crc    | SHT4x CRC-8 알고리즘으로 데이터 무결성 검증
# read_sht41      | SHT41에서 온도/습도 측정 후 반환 (CRC 검증 포함)
#
# 입력값(파라미터 타입)
# - select_channel(bus: SMBus, ch: int)
# - validate_crc(data_bytes: list[int], crc_value: int)
# - read_sht41(bus: SMBus)
#
# 반환값
# - select_channel(): None
# - validate_crc(): bool
# - read_sht41(): tuple[float, float]
#
# 주의사항/로직 요약
# - CRC 오류 또는 길이 오류 발생 시 예외 발생
# - PCA9548A 주소와 채널 번호 반드시 확인
# - I²C 통신 실패 시 OSError 발생 가능

#!/usr/bin/env python3
"""
BME280.py
────────────────────────────────────────────────────────
- Raspberry Pi I²C-1(메인 버스)에 직접 연결된 BME280(0x76) 읽기 유틸
- Chip ID 확인 → 드라이버 초기화 → 실제 고도 기반 sea_level_pressure 보정

!! 주의 사항 !!
1) I²C 활성화 필요: raspi-config → Interface Options → I2C → Enable
2) BME280 주소(0x76/0x77)는 모듈에 따라 다를 수 있음 (본 예시는 0x76)
3) 첫 측정은 안정화 지연(0.5 s)을 고려하여 보정값 계산

📌 사용법
- 단독 실행(테스트): `python3 BME280.py` (콘솔 로그 출력)
- 외부 import 사용: `check_chip()`, `auto_calibrate()` 호출 (기본은 조용히 동작)
"""

import time
from smbus2 import SMBus
import board
import busio
from adafruit_bme280.basic import Adafruit_BME280_I2C

# ───────── 설정값 ─────────
BME280_ADDR   = 0x76
CHIP_ID_REG   = 0xD0
READ_INTERVAL = 2           # sec (단독 테스트에서만 사용)
TRUE_ALT_M    = 26.0        # 지도‧GPS로 확인한 실제 고도(m)

# =====================================================
# 1️⃣ 센서 존재 확인 (Chip ID 검사)
# =====================================================
def check_chip(verbose: bool = False) -> bool:
    """
    BME280 Chip ID(0x60) 확인.

    Args:
        verbose (bool): True면 콘솔에 감지/오류 메시지 출력

    Returns:
        bool: BME280이 정상 응답하고 Chip ID가 0x60이면 True
    """
    with SMBus(1) as bus:
        try:
            cid = bus.read_byte_data(BME280_ADDR, CHIP_ID_REG)
            if cid == 0x60:
                if verbose:
                    print(f"✅  BME280 감지 (Chip ID 0x{cid:02X})")
                return True
            else:
                if verbose:
                    print(f"❌  Chip ID 0x{cid:02X} (BME280 아님)")
                return False
        except Exception as e:
            if verbose:
                print(f"❌  BME280 접근 실패: {e}")
            return False

# =====================================================
# 2️⃣ sea-level 기압 자동 보정
# =====================================================
def auto_calibrate(bme: Adafruit_BME280_I2C, true_alt: float = TRUE_ALT_M, verbose: bool = False) -> None:
    """
    실제 고도(m)를 이용해 해수면 기준 기압(sea_level_pressure)을 계산/적용.

    Args:
        bme (Adafruit_BME280_I2C): 초기화된 BME280 객체
        true_alt (float): 설치 지점의 실제 고도(m)
        verbose (bool): True면 보정값/추정 고도 출력
    """
    # 첫 측정이 안정될 때까지 0.5 s 대기
    time.sleep(0.5)
    measured_p = bme.pressure        # hPa
    sea_level = measured_p / (1 - true_alt/44330) ** 5.255
    bme.sea_level_pressure = sea_level
    if verbose:
        print(f"🔧 sea_level_pressure 보정  →  {sea_level:.2f} hPa")
        print(f"   보정 후 altitude ≈ {bme.altitude:.2f} m")

# =====================================================
# 3️⃣ 단독 테스트용 메인 루프 (import 시 실행되지 않음)
# =====================================================
def main():
    """
    BME280 단독 테스트 루틴 (로그 출력 포함).
    """
    if not check_chip(verbose=True):
        return

    i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
    bme = Adafruit_BME280_I2C(i2c, address=BME280_ADDR)

    auto_calibrate(bme, TRUE_ALT_M, verbose=True)

    try:
        while True:
            print(
                f"🌡️ {bme.temperature:6.2f} °C   "
                f"💧 {bme.humidity:5.2f} %RH   "
                f"📈 {bme.pressure:7.2f} hPa   "
                f"📏 alt {bme.altitude:6.2f} m"
            )
            time.sleep(READ_INTERVAL)
    except KeyboardInterrupt:
        print("\n종료합니다.")

if __name__ == "__main__":
    main()

# ─────────────────────────────────────────────────────
# 함수 인벤토리 (요약 표)
# ─────────────────────────────────────────────────────
# 함수명         | 기능 설명
# -------------- | --------------------------------------------
# check_chip     | Chip ID(0x60) 확인 (verbose 선택)
# auto_calibrate | 실제 고도로 sea_level_pressure 보정 (verbose 선택)
# main           | 단독 테스트 루프(로그 출력)
#
# 입력값/반환값
# - check_chip(verbose: bool=False) -> bool
# - auto_calibrate(bme: Adafruit_BME280_I2C, true_alt: float=26.0, verbose: bool=False) -> None
# - main() -> None
#
# 주의사항/로직 요약
# - 예외 처리: check_chip에서 I²C 접근 예외 처리
# - 외부 호출: smbus2, Adafruit_BME280_I2C, busio.I2C
# - 부작용: verbose=True일 때만 콘솔 출력

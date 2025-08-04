#!/usr/bin/env python3
"""
BME280(0x76) · ADS1115(0x48) · PCA9548A(0x74)
BME280은 메인 I2C-1 버스에 직접 연결해 쓰는 예시.
"""

import time
from smbus2 import SMBus
import board
import busio
from adafruit_bme280.basic import Adafruit_BME280_I2C

# ───────── 설정값 ─────────
BME280_ADDR   = 0x76
CHIP_ID_REG   = 0xD0
READ_INTERVAL = 2          # sec
TRUE_ALT_M    = 26.0       # ↼ 지도‧GPS로 확인한 실제 고도(m)

# ───────── 센서 존재 확인 ─────────
def check_chip():
    with SMBus(1) as bus:
        try:
            cid = bus.read_byte_data(BME280_ADDR, CHIP_ID_REG)
            if cid == 0x60:
                print(f"✅  BME280 감지 (Chip ID 0x{cid:02X})")
                return True
            print(f"❌  Chip ID 0x{cid:02X} (BME280 아님)")
        except Exception as e:
            print(f"❌  센서 접근 실패: {e}")
    return False

# ───────── sea-level 기압 자동 보정 ─────────
def auto_calibrate(bme, true_alt=TRUE_ALT_M):
    # 첫 측정이 안정될 때까지 0.5 s 대기
    time.sleep(0.5)
    measured_p = bme.pressure        # hPa
    sea_level = measured_p / (1 - true_alt/44330) ** 5.255
    bme.sea_level_pressure = sea_level
    print(f"🔧 sea_level_pressure 보정  →  {sea_level:.2f} hPa")
    print(f"   보정 후 altitude ≈ {bme.altitude:.2f} m\n")

# ───────── 메인 루프 ─────────
def main():
    if not check_chip():                         # ① Chip ID 확인
        return

    # ② I2C 버스 / 센서 객체
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
    bme = Adafruit_BME280_I2C(i2c, address=BME280_ADDR)

    # ③ 자동 보정 (지형 고도 → sea_level_pressure 계산)
    auto_calibrate(bme, TRUE_ALT_M)

    # ④ 지속 측정
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

'''
#!/usr/bin/env python3
"""
BME280  (주소 0x76)  ──┐
ADS1115(주소 0x48)  ──┤──> Raspberry Pi  I²C-1  (SDA, SCL)
PCA9548A(주소 0x74) ──┘      └─ 다른 센서들은 MUX 채널에서 사용
"""

import time
from smbus2 import SMBus
import board
import busio
from adafruit_bme280.basic import Adafruit_BME280_I2C

# ──────────────── 설정 ────────────────
BME280_ADDR  = 0x76     # 센서 I²C 주소
CHIP_ID_REG  = 0xD0     # ID 레지스터
SEA_LEVEL_HPA = 1013.25 # 고도 계산용 기준 기압
READ_INTERVAL = 2       # 초

# ──────────────── 초기 확인 ─────────────
def check_chip_id():
    with SMBus(1) as bus:
        try:
            chip_id = bus.read_byte_data(BME280_ADDR, CHIP_ID_REG)
            if chip_id == 0x60:
                print(f"✅  BME280 감지됨 (Chip ID: 0x{chip_id:02X})")
                return True
            else:
                print(f"❌  예상치 못한 Chip ID: 0x{chip_id:02X}  (BME280 아님)")
                return False
        except Exception as e:
            print(f"❌  BME280 접근 실패: {e}")
            return False

# ──────────────── 측정 루프 ─────────────
def main():
    if not check_chip_id():
        return

    # Pi 의 기본 I²C-1 버스 (100 kHz 권장)
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)

    # Adafruit 드라이버로 BME280 객체 생성
    bme = Adafruit_BME280_I2C(i2c, address=BME280_ADDR)
    bme.sea_level_pressure = SEA_LEVEL_HPA  # 고도 보정 기준 기압

    try:
        while True:
            print(
                f"🌡️  {bme.temperature:6.2f} °C   "
                f"💧 {bme.humidity:5.2f} %RH   "
                f"📈 {bme.pressure:7.2f} hPa   "
                f"📏 alt {bme.altitude:6.2f} m"
            )
            time.sleep(READ_INTERVAL)
    except KeyboardInterrupt:
        print("\n종료합니다.")

if __name__ == "__main__":
    main()
'''
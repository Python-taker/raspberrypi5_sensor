import time
from smbus2 import SMBus, i2c_msg

# ─── 주소 정의 ─────────────────────────────
PCA9548A_ADDR = 0x74       # PCA9548A I2C 주소 (A2=HIGH이면 0x74)
SHT41_ADDR    = 0x44       # SHT4x 센서 고정 주소
TARGET_CHANNEL = 1         # SHT41은 채널 1번에 연결됨

# ─── 채널 선택 ─────────────────────────────
def select_channel(bus, ch):
    bus.write_byte(PCA9548A_ADDR, 1 << ch)
    time.sleep(0.05)

# ─── 센서 측정 ─────────────────────────────
def read_sht41(bus):
    # 고정밀 측정 명령 (0xFD)
    bus.write_byte(SHT41_ADDR, 0xFD)
    time.sleep(0.5)  # 최대 0.5초 대기 (데이터 준비 시간)

    # 데이터 읽기 (6바이트: T[2]+CRC + RH[2]+CRC)
    read = i2c_msg.read(SHT41_ADDR, 6)
    bus.i2c_rdwr(read)
    data = list(read)

    if len(data) != 6:
        raise RuntimeError("센서 데이터 길이 오류")

    # CRC 확인 (옵션이지만 안정성을 위해 사용)
    if not validate_crc(data[:2], data[2]) or not validate_crc(data[3:5], data[5]):
        raise ValueError("CRC 오류 발생")

    t_raw = (data[0] << 8) | data[1]
    h_raw = (data[3] << 8) | data[4]

    # 데이터 변환 공식 (Datasheet 기준)
    temperature = -45 + (175 * (t_raw / 65535.0))
    humidity = 100 * (h_raw / 65535.0)

    return round(temperature, 1), round(humidity, 1)

# ─── CRC 확인 함수 (SHT4x CRC-8) ─────────────
def validate_crc(data_bytes, crc_value):
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

# ─── 메인 루프 ─────────────────────────────
if __name__ == '__main__':
    with SMBus(1) as bus:
        print(f"\n🔀 채널 {TARGET_CHANNEL} 선택")
        select_channel(bus, TARGET_CHANNEL)

        try:
            temp, hum = read_sht41(bus)
            print(f"✅ SHT41 측정 결과: {temp} °C, {hum}% RH")
        except Exception as e:
            print(f"❌ SHT41 오류: {e}")

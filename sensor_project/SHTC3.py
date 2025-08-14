import time
from smbus2 import SMBus, i2c_msg

# ─── 주소 정의 ─────────────────────────────
PCA9548A_ADDR = 0x74        # 멀티플렉서 주소 (A2=HIGH → 0x71)
SHTC3_ADDR    = 0x70        # SHTC3 고정 주소
TARGET_CHANNELS = [2,3,4,5]   # 읽고 싶은 채널들

# ─── CRC‑8 (Sensirion) ─────────────────────
def crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc

# ─── 보조 함수들 ───────────────────────────
def select_channel(bus, ch):
    bus.write_byte(PCA9548A_ADDR, 1 << ch)
    time.sleep(0.05)

def wake_sensor(bus):
    bus.write_i2c_block_data(SHTC3_ADDR, 0x35, [0x17])
    time.sleep(0.2)

def sleep_sensor(bus):
    bus.write_i2c_block_data(SHTC3_ADDR, 0xB0, [0x98])
    time.sleep(0.01)

def reset_sensor(bus):
    bus.write_i2c_block_data(SHTC3_ADDR, 0x80, [0x5D])
    time.sleep(0.05)

def verify_wake(bus):
    try:
        bus.write_i2c_block_data(SHTC3_ADDR, 0xEF, [0xC8])
        time.sleep(0.01)
        read = i2c_msg.read(SHTC3_ADDR, 3)
        bus.i2c_rdwr(read)
        id_bytes = list(read)
        print(f"    🆔 ID raw: {id_bytes}")
        return len(id_bytes) == 3 and crc8(id_bytes[:2]) == id_bytes[2]
    except Exception:
        return False

def measure(bus):
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

# ─── 센서 1개 읽기 시퀀스 ───────────────────
def read_single_sensor(bus):
    reset_sensor(bus)
    wake_sensor(bus)
    if not verify_wake(bus):
        raise RuntimeError("센서 wake 실패 또는 ID CRC 불일치")
    temp, hum = measure(bus)
    sleep_sensor(bus)
    return temp, hum

# ─── 메인 루프 ─────────────────────────────
if __name__ == '__main__':
    with SMBus(1) as bus:
        for ch in TARGET_CHANNELS:
            print(f"\n🔀 채널 {ch} 선택")
            select_channel(bus, ch)

            try:
                temp, hum = read_single_sensor(bus)
                print(f"✅ CH{ch}: {temp} °C, {hum}% RH")
            except Exception as e:
                print(f"❌ CH{ch} 오류: {e}")
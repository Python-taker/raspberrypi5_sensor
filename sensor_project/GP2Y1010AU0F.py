#!/usr/bin/env python3
"""
GP2Y1010AU0F 미세먼지 센서 (아날로그 출력)
- ADS1115 A0 입력 (0x48) → Raspberry Pi I2C-1
- IR-LED 제어선 → GPIO 18 (BCM) - µs 단위 제어 (lgpio 사용)
"""

import time
import lgpio
import board, busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import statistics

# ───────── 사용자 설정 ─────────
LED_PIN        = 18         # BCM 핀 번호
NO_DUST_VOLT   = 0.0078     # 보정된 무먼지 기준 전압(V)
GAIN           = 1          # ±4.096V
CYCLE_MS       = 10         # 센서 주기 10ms
SAMPLES        = 10         # 샘플 수 증가 → 평균 정확도 향상
MAX_VALID_UG   = 500       # 이상값 제한

# ───────── GPIO 초기화 ─────────
handle = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(handle, LED_PIN, 1)  # HIGH = LED OFF

# ───────── ADS1115 초기화 ─────────
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c, gain=GAIN, data_rate=860)
chan = AnalogIn(ads, ADS.P0)

# ───────── 이상치 제거 함수 ─────────
def reject_outliers(data, m=2.0):
    if len(data) < 2:
        return data
    mean = statistics.mean(data)
    stdev = statistics.stdev(data)
    return [v for v in data if abs(v - mean) <= m * stdev]

# ───────── 센서 측정 함수 ─────────
def read_dust():
    voltages = []

    for _ in range(SAMPLES):
        # ① LED ON
        lgpio.gpio_write(handle, LED_PIN, 0)
        time.sleep(0.00028)  # 280 µs

        # ② 전압 측정
        v = chan.voltage
        v = max(0.0, v)  # 음수 제거
        voltages.append(v)

        # ③ LED OFF + 대기
        time.sleep(0.00004)
        lgpio.gpio_write(handle, LED_PIN, 1)
        time.sleep((CYCLE_MS / 1000) - 0.00032)

    # ④ 이상치 제거 후 평균
    voltages = reject_outliers(voltages)
    if voltages:
        avg_v = sum(voltages) / len(voltages)
    else:
        avg_v = 0.0

    # ⑤ 먼지 계산
    density_mg = max(0.0, (avg_v - NO_DUST_VOLT) / 0.005)
    density_ug = density_mg * 1000

    # ⑥ 최대값 제한
    if density_ug > MAX_VALID_UG:
        density_ug = 0

    return avg_v, density_ug

# ───────── 메인 루프 ─────────
try:
    print("♻  Ctrl-C 로 종료 (측정 시작)\n")
    while True:
        vout, dust = read_dust()
        print(f"🔎 Vout = {vout:7.5f} V   Dust = {dust:7.1f} µg/m³")
except KeyboardInterrupt:
    pass
finally:
    lgpio.gpiochip_close(handle)

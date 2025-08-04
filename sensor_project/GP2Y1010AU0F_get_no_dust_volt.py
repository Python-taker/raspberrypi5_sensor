#!/usr/bin/env python3
"""
GP2Y1010AU0F 센서 무먼지 기준 전압 측정용
IR-LED 주기적 토글 + ADS1115로 아날로그 전압 읽기
"""

import time
import lgpio
import board, busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ───────── 사용자 설정 ─────────
LED_PIN     = 18
GAIN        = 1
CYCLE_MS    = 10       # 10ms = 100Hz
NUM_READS   = 50       # 측정 횟수 (평균 추출용)

# ───────── 초기화 ─────────
handle = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(handle, LED_PIN, 1)  # HIGH = LED OFF

i2c  = busio.I2C(board.SCL, board.SDA)
ads  = ADS.ADS1115(i2c, gain=GAIN, data_rate=860)
chan = AnalogIn(ads, ADS.P0)

# ───────── 로깅 시작 ─────────
vout_list = []
print(f"📡 {NUM_READS}회 측정 중... (Ctrl-C 중지)\n")

try:
    for i in range(NUM_READS):
        # ① LED ON (LOW)
        lgpio.gpio_write(handle, LED_PIN, 0)
        time.sleep(0.00028)

        # ② 아날로그 전압 측정
        vout = chan.voltage
        vout_list.append(vout)

        # ③ LED OFF 및 주기 정렬
        time.sleep(0.00004)
        lgpio.gpio_write(handle, LED_PIN, 1)
        time.sleep((CYCLE_MS / 1000) - 0.00032)

        # 출력
        print(f"[{i+1:02}] Vout = {vout:.5f} V")

except KeyboardInterrupt:
    print("\n⏹ 중단됨.")

finally:
    lgpio.gpiochip_close(handle)
    if vout_list:
        avg_v = sum(vout_list) / len(vout_list)
        print(f"\n📊 평균 무먼지 전압 (NO_DUST_VOLT): {avg_v:.5f} V")
    else:
        print("\n⚠ 측정된 값이 없습니다.")

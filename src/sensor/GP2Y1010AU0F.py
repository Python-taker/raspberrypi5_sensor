#!/usr/bin/env python3
"""
GP2Y1010AU0F.py
────────────────────────────────────────────────────────
- Sharp GP2Y1010AU0F 미세먼지 센서의 아날로그 출력을 ADS1115(A0)로 읽어 미세먼지 농도 계산
- IR LED 구동 핀(GPIO 18, BCM)을 µs 단위로 제어하여 센서 주기 맞춤 동작
- 이상치 제거 후 평균 전압 → 농도(µg/m³) 변환

!! 주의 사항 !!
1) ADS1115 주소(기본 0x48)와 연결 채널(P0) 확인
2) IR LED 제어 핀의 타이밍(280µs ON + 40µs OFF) 엄격 준수
3) NO_DUST_VOLT, 변환계수(0.005 V/mg/m³)는 환경에 맞춰 교정 가능
4) MAX_VALID_UG 이상 측정값은 이상치로 간주하고 0 처리

📌 호출 관계 및 사용법
- 단독 실행: `python3 GP2Y1010AU0F.py`
- 다른 모듈에서 import 시:
    from .GP2Y1010AU0F import init, read_dust, close
    init()는 자동으로 호출되므로 보통 직접 호출 불필요
"""

import time
import atexit
import statistics
import lgpio
import board, busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ───────── 사용자 설정 ─────────
LED_PIN        = 18         # BCM 핀 번호 (IR LED 제어)
NO_DUST_VOLT   = 0.0078     # 무먼지 기준 전압(V) (환경 보정 필요)
GAIN           = 1          # ADS1115 입력 전압 범위 ±4.096V
CYCLE_MS       = 10         # 센서 주기 (10ms)
SAMPLES        = 10         # 샘플 수 (평균 정확도 향상)
MAX_VALID_UG   = 500        # 최대 유효 농도(µg/m³), 초과 시 0 처리

# ───────── 내부 상태(지연 초기화) ─────────
_handle = None
_i2c = None
_ads = None
_chan = None
_atexit_registered = False

# =====================================================
# 0️⃣ 초기화 / 종료
# =====================================================
def init(verbose: bool = False):
    """
    GPIO 및 ADS1115를 초기화(여러 번 호출돼도 안전).
    """
    global _handle, _i2c, _ads, _chan, _atexit_registered
    if _handle is None:
        _handle = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(_handle, LED_PIN, 1)  # HIGH = LED OFF
        if verbose:
            print("🔌 GP2Y GPIO init done")

    if _i2c is None:
        _i2c = busio.I2C(board.SCL, board.SDA)
        _ads = ADS.ADS1115(_i2c, gain=GAIN, data_rate=860)
        _chan = AnalogIn(_ads, ADS.P0)
        if verbose:
            print("🧰 ADS1115 init done")

    if not _atexit_registered:
        atexit.register(close)
        _atexit_registered = True

def close():
    """
    GPIO/I2C/ADS 리소스 정리(중복 호출 안전).
    """
    global _handle, _i2c, _ads, _chan
    try:
        if _handle is not None:
            # LED OFF 상태로 두고 close
            try:
                lgpio.gpio_write(_handle, LED_PIN, 1)
            except Exception:
                pass
            lgpio.gpiochip_close(_handle)
    except Exception:
        pass
    finally:
        _handle = None

    # Blinka busio.I2C는 일부 환경에서 deinit 제공
    try:
        if _i2c is not None and hasattr(_i2c, "deinit"):
            _i2c.deinit()
    except Exception:
        pass
    finally:
        _i2c = None
        _ads = None
        _chan = None

# =====================================================
# 1️⃣ 이상치 제거
# =====================================================
def reject_outliers(data, m=2.0):
    """
    평균 ± m*표준편차 범위 밖의 값 제거.

    Args:
        data (list[float])
        m (float): 표준편차 배수 (기본=2.0)

    Returns:
        list[float]
    """
    if len(data) < 2:
        return data
    mean = statistics.mean(data)
    stdev = statistics.stdev(data)
    return [v for v in data if abs(v - mean) <= m * stdev]

# =====================================================
# 2️⃣ 센서 1회 측정
# =====================================================
def read_dust(verbose: bool = False):
    """
    GP2Y1010AU0F 센서에서 미세먼지 농도 1회 측정.

    Returns:
        tuple[float, float]: (평균 전압[V], 농도[µg/m³])
    """
    if _handle is None or _chan is None:
        init(verbose=False)

    voltages = []

    for _ in range(SAMPLES):
        # ① LED ON
        lgpio.gpio_write(_handle, LED_PIN, 0)
        time.sleep(0.00028)  # 280 µs

        # ② 전압 측정
        v = _chan.voltage
        v = max(0.0, v)  # 음수 제거
        voltages.append(v)

        # ③ LED OFF + 대기
        time.sleep(0.00004)
        lgpio.gpio_write(_handle, LED_PIN, 1)
        time.sleep((CYCLE_MS / 1000) - 0.00032)

    # ④ 이상치 제거 후 평균
    voltages = reject_outliers(voltages)
    avg_v = sum(voltages) / len(voltages) if voltages else 0.0

    # ⑤ 먼지 농도 계산
    density_mg = max(0.0, (avg_v - NO_DUST_VOLT) / 0.005)
    density_ug = density_mg * 1000

    # ⑥ 최대값 제한
    if density_ug > MAX_VALID_UG:
        density_ug = 0

    if verbose:
        print(f"🔎 Vout={avg_v:0.5f} V, Dust={density_ug:0.1f} µg/m³")

    return avg_v, density_ug

# =====================================================
# 3️⃣ 단독 실행(테스트) — import 시에는 실행되지 않음
# =====================================================
if __name__ == "__main__":
    try:
        init(verbose=True)
        print("♻  Ctrl-C 로 종료 (측정 시작)\n")
        while True:
            vout, dust = read_dust(verbose=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        close()

# ─────────────────────────────────────────────────────
# 함수 인벤토리 (요약 표)
# ─────────────────────────────────────────────────────
# 함수명          | 기능 설명
# --------------- | ----------------------------------------------------------
# init            | GPIO/ADS1115 지연 초기화(중복 호출 안전)
# reject_outliers | 표준편차 기반 이상치 제거
# read_dust       | IR LED 제어 + ADS1115 전압 측정 → 농도 계산 (verbose 선택)
# close           | GPIO/디바이스 핸들 정리
#
# 입력값(파라미터 타입)
# - init(verbose: bool=False)
# - reject_outliers(data: list[float], m: float=2.0)
# - read_dust(verbose: bool=False)
# - close()
#
# 반환값
# - init(): None
# - reject_outliers(): list[float]
# - read_dust(): tuple[float, float]
# - close(): None
#
# 주의사항/로직 요약
# - LED ON/OFF 타이밍을 µs 단위로 준수
# - NO_DUST_VOLT, 변환계수는 현장 교정 필요
# - MAX_VALID_UG 초과 값은 0 처리
# - import 시엔 로그/루프 없음, 종료 시 close()로 정리

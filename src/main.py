#!/usr/bin/env python3
"""
src/main.py
────────────────────────────────────────────────────────
- 멀티스레드 센서 수집 + 10초 윈도우 집계(평균/절사평균/중앙값) + MQTT 발행
- I2C 경합 방지: 공용 i2c_lock 사용
- 실행: 프로젝트 루트(~/ssafy_project)에서  `python -m src.main`
"""

import os
import json
import time
import threading
from collections import deque
from datetime import datetime
import statistics

# ── 환경변수(.env) & 브로커/토픽 ──
from dotenv import load_dotenv
load_dotenv()

# ✅ config.py가 src/ 안에 있는 표준 경로
try:
    from .config import TOPICS_PUB
# 🔙 레거시 호환 (다른 머신에서 루트에 있을 때도 동작)
except ImportError:
    from config import TOPICS_PUB

BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# ── MQTT 클라이언트 ──
from .mqtt_client import MQTTClient

# ── 센서 모듈 ──
from smbus2 import SMBus
from .sensor import BME280 as bme280_mod
from .sensor import SHT41 as sht41_mod
from .sensor import SHTC3 as shtc3_mod
from .sensor import GP2Y1010AU0F as gp2y_mod
try:
    from .sensor import MH_Z19B as mhz_mod
except ImportError:
    from .sensor import ZH_19B as mhz_mod  # 파일명이 ZH_19B.py인 경우

# =====================================================
# 전역 동기화/상태
# =====================================================
i2c_lock = threading.Lock()
state_lock = threading.Lock()
stop_event = threading.Event()

latest = {
    "timestamp": None,
    "bme280": None,
    "sht41": None,
    "shtc3": {},
    "gp2y": None,
    "mhz19b": None,
}

# =====================================================
# 집계 버퍼(10초 윈도우)
# =====================================================
BUF_WINDOW_S = 10
TRIM_FRAC = 0.10
MIN_SAMPLES_FOR_TRIM = 5

MIN_REQUIRED = {
    "slot": 2,  # 각 슬롯 평균에 필요한 최소 표본
    "co2": 2,
    "pm25": 5,
    "pres": 2,
}

buf = {
    "temp_slots": {0: deque(), 1: deque(), 2: deque(), 3: deque()},
    "rh_slots":   {0: deque(), 1: deque(), 2: deque(), 3: deque()},
    "bme_temp": deque(),
    "bme_rh":   deque(),
    "bme_pres": deque(),
    "co2":      deque(),
    "pm25":     deque(),
}

def _push(ts, key, val, slot=None):
    if val is None:
        return
    if slot is None:
        buf[key].append((ts, val))
    else:
        buf[key][slot].append((ts, val))

def _prune_now(now):
    cutoff = now - BUF_WINDOW_S
    for v in buf.values():
        if isinstance(v, dict):
            for d in v.values():
                while d and d[0][0] < cutoff:
                    d.popleft()
        else:
            while v and v[0][0] < cutoff:
                v.popleft()

def _mean_safe(values):
    return None if not values else round(sum(values) / len(values), 2)

def _median_safe(values):
    return None if not values else round(statistics.median(values), 2)

def _trimmed_mean_safe(values, frac: float = TRIM_FRAC):
    if not values:
        return None
    n = len(values)
    if n < MIN_SAMPLES_FOR_TRIM:
        return round(sum(values) / n, 2)
    k = int(n * frac)
    if k == 0:
        return round(sum(values) / n, 2)
    vals = sorted(values)[k:n - k]
    if not vals:
        return round(sum(values) / n, 2)
    return round(sum(vals) / len(vals), 2)

# =====================================================
# Worker A: SHT41(Ch1) + SHTC3(Ch2~5)
# =====================================================
def worker_mux_shts(period_s: float = 1.0):
    ch_sht41 = sht41_mod.TARGET_CHANNEL
    ch_list_shtc3 = shtc3_mod.TARGET_CHANNELS
    while not stop_event.is_set():
        try:
            with i2c_lock:
                sht41_mod.select_channel(_smbus, ch_sht41)
                t, h = sht41_mod.read_sht41(_smbus)
            with state_lock:
                latest["sht41"] = {"temp_c": t, "rh": h}
        except Exception as e:
            with state_lock:
                latest["sht41"] = None
            print(f"❌ SHT41 error: {e}")

        for ch in ch_list_shtc3:
            try:
                with i2c_lock:
                    shtc3_mod.select_channel(_smbus, ch)
                    t, h = shtc3_mod.read_single_sensor(_smbus)
                with state_lock:
                    latest["shtc3"][ch] = {"temp_c": t, "rh": h}
            except Exception as e:
                with state_lock:
                    latest["shtc3"][ch] = None
                print(f"❌ SHTC3 ch{ch} error: {e}")
        time.sleep(period_s)

# =====================================================
# Worker B: BME280 + GP2Y
# =====================================================
def worker_bme_gp2y(period_s: float = 1.0):
    try:
        if not bme280_mod.check_chip():
            print("❌ BME280 not found")
        import board, busio
        from adafruit_bme280.basic import Adafruit_BME280_I2C
        with i2c_lock:
            _i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
            _bme = Adafruit_BME280_I2C(_i2c, address=bme280_mod.BME280_ADDR)
            bme280_mod.auto_calibrate(_bme, bme280_mod.TRUE_ALT_M)
    except Exception as e:
        print(f"❌ BME280 init error: {e}")
        _bme = None

    while not stop_event.is_set():
        try:
            if _bme:
                with i2c_lock:
                    temp = _bme.temperature
                    hum  = _bme.humidity
                    pres = _bme.pressure
                    alt  = _bme.altitude
                with state_lock:
                    latest["bme280"] = {
                        "temp_c": round(temp, 2),
                        "rh": round(hum, 2),
                        "press_hpa": round(pres, 2),
                        "alt_m": round(alt, 2),
                    }
        except Exception as e:
            with state_lock:
                latest["bme280"] = None
            print(f"❌ BME280 read error: {e}")

        try:
            with i2c_lock:
                vout, ug = gp2y_mod.read_dust()
            with state_lock:
                latest["gp2y"] = {"vout": round(vout, 5), "pm_ugm3": round(ug, 1)}
        except Exception as e:
            with state_lock:
                latest["gp2y"] = None
            print(f"❌ GP2Y read error: {e}")

        time.sleep(period_s)

# =====================================================
# Worker C: MH-Z19B (UART)
# =====================================================
def worker_mhz(period_s: float = 2.5):
    try:
        ser = mhz_mod.init()
    except Exception as e:
        print(f"❌ MH-Z19B init error: {e}")
        ser = None

    while not stop_event.is_set():
        try:
            result = mhz_mod.read_mhz19(ser) if ser else None
            if result:
                co2, temp, _ = result
            else:
                if getattr(mhz_mod, "last_valid_result", None):
                    co2, temp, _ = mhz_mod.last_valid_result
                else:
                    co2, temp = None, None
            with state_lock:
                latest["mhz19b"] = None if co2 is None else {"co2": int(co2), "temp": int(temp)}
        except Exception as e:
            with state_lock:
                latest["mhz19b"] = None
            print(f"❌ MH-Z19B read error: {e}")

        time.sleep(period_s)

# =====================================================
# Publisher
# =====================================================
def publisher(period_s: float = 1.0):
    mqtt = MQTTClient(BROKER_HOST, BROKER_PORT, publish_topics=TOPICS_PUB)
    try:
        mqtt.connect()
        print(f"🔗 MQTT connected to {BROKER_HOST}:{BROKER_PORT}, topics={TOPICS_PUB}")
    except Exception as e:
        print(f"❌ MQTT connect error: {e}")
        return

    first_window_start = None
    t0 = time.monotonic()

    while not stop_event.is_set():
        now = time.monotonic()

        with state_lock:
            snap = dict(latest)
        ts = now

        # 최신 스냅샷을 버퍼에 적재
        s3 = snap.get("shtc3") or {}
        ch_to_slot = {2: 0, 3: 1, 4: 2, 5: 3}
        for ch, slot in ch_to_slot.items():
            e = s3.get(ch)
            if e:
                _push(ts, "temp_slots", e.get("temp_c"), slot)
                _push(ts, "rh_slots",   e.get("rh"), slot)

        b = snap.get("bme280")
        if b:
            _push(ts, "bme_temp", b.get("temp_c"))
            _push(ts, "bme_rh",   b.get("rh"))
            _push(ts, "bme_pres", b.get("press_hpa"))

        mh = snap.get("mhz19b")
        if mh:
            _push(ts, "co2", mh.get("co2"))

        gp = snap.get("gp2y")
        if gp:
            _push(ts, "pm25", gp.get("pm_ugm3"))

        _prune_now(now)

        # 웜업: 최초 샘플 들어온 뒤 10초 경과 후 첫 발행
        if first_window_start is None:
            have_slot = any(len(dq) >= 1 for dq in buf["temp_slots"].values())
            have_co2  = len(buf["co2"]) >= 1
            have_pm   = len(buf["pm25"]) >= 1
            have_pres = len(buf["bme_pres"]) >= 1
            if have_slot or have_co2 or have_pm or have_pres:
                first_window_start = now

        # 10초마다 집계·발행
        if first_window_start is not None and (now - t0) >= BUF_WINDOW_S and (now - first_window_start) >= BUF_WINDOW_S:
            t0 = now

            def vals(dq): return [v for _, v in dq]

            # 슬롯별 평균 (표본 부족 시 None)
            temp_slots = []
            rh_slots   = []
            for i in range(4):
                vs_t = vals(buf["temp_slots"][i])
                vs_h = vals(buf["rh_slots"][i])
                temp_slots.append(_mean_safe(vs_t) if len(vs_t) >= MIN_REQUIRED["slot"] else None)
                rh_slots.append(_mean_safe(vs_h)   if len(vs_h) >= MIN_REQUIRED["slot"] else None)

            # CO₂ 중앙값 / PM2.5 절사평균 / 압력 평균
            co2_vals = vals(buf["co2"])
            pm_vals  = vals(buf["pm25"])
            pr_vals  = vals(buf["bme_pres"])

            co2_aggr   = _median_safe(co2_vals)      if len(co2_vals) >= MIN_REQUIRED["co2"]  else None
            pm25_aggr  = _trimmed_mean_safe(pm_vals) if len(pm_vals)  >= MIN_REQUIRED["pm25"] else None
            pres_aggr  = _mean_safe(pr_vals)         if len(pr_vals)  >= MIN_REQUIRED["pres"] else None

            # ── 타입 강제 변환 도우미 ──
            def f4_float(lst):
                # None -> 0.0, 길이 4 보장
                base = [(float(x) if x is not None else 0.0) for x in lst]
                return (base + [0.0, 0.0, 0.0, 0.0])[:4]

            def single_to4_int(v):
                # None -> 0, 정수 4칸 (첫 칸만 값)
                return [int(round(v)) if v is not None else 0, 0, 0, 0]

            def single_to4_float(v):
                # None -> 0.0, 실수 4칸 (첫 칸만 값)
                return [float(v) if v is not None else 0.0, 0.0, 0.0, 0.0]

            # 최종 배열 생성 (요구 스펙에 맞춰 타입 보장)
            temp_arr = f4_float(temp_slots)
            rh_arr   = f4_float(rh_slots)
            co2_arr  = single_to4_int(co2_aggr)
            pm25_arr = single_to4_int(pm25_aggr)     # pm25는 정수 전송
            pres_arr = single_to4_float(pres_aggr)

            payload = {
                "hvac_id": 1,
                "data": {
                    "temperature": temp_arr,   # float[4]
                    "humidity":    rh_arr,     # float[4]
                    "co2":         co2_arr,    # int[4]
                    "pm25":        pm25_arr,   # int[4]
                    "pressure":    pres_arr,   # float[4]
                },
            }

            msg = json.dumps(payload, ensure_ascii=False)
            for topic, qos in TOPICS_PUB:
                try:
                    print(f"📤 MQTT → {topic} | {datetime.now().isoformat(timespec='seconds')}")
                    mqtt.publish(topic, msg, qos=qos)
                except Exception as e:
                    print(f"❌ MQTT publish error ({topic}): {e}")

        time.sleep(period_s)

# =====================================================
# 엔트리포인트
# =====================================================
if __name__ == "__main__":
    _smbus = SMBus(1)

    threads = [
        threading.Thread(target=worker_mux_shts, name="MUX_SHTS", daemon=True),
        threading.Thread(target=worker_bme_gp2y, name="BME_GP2Y", daemon=True),
        threading.Thread(target=worker_mhz,     name="MHZ19B",    daemon=True),
        threading.Thread(target=publisher,      name="PUBLISHER", daemon=True),
    ]

    try:
        for t in threads:
            t.start()
        print(f"✅ Sensors started. MQTT {BROKER_HOST}:{BROKER_PORT}. Press Ctrl-C to stop.")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n👋 Stopping...")
        stop_event.set()
        for t in threads:
            t.join(timeout=2.0)
        _smbus.close()
        print("🧹 Clean exit.")

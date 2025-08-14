# SSAFY Sensor Project (Raspberry Pi 5 기준)

본 프로젝트는 Raspberry Pi 5 기반에서 `.venv` 가상환경을 사용하여 다양한 센서(BME280, SHT41, SHTC3 x4, GP2Y1010AU0F, ADS1115, MH-Z19B 등)를 제어하고, 수집된 데이터를 MQTT 프로토콜로 전송하는 시스템입니다.

---

## 📑 목차

* [빠른 실행](#-빠른-실행)
* [사전 요구사항](#-사전-요구사항)
* [설치 및 환경 구성](#-설치-및-환경-구성)
* [UART 문제 해결](#uart-문제-해결)
* [센서 목록 및 기능](#-센서-목록-및-기능)
* [하드웨어 연결](#하드웨어-연결-라즈베리파이-기준)
* [백업 및 복원](#-백업-및-복원)
* [자동 실행](#-자동-실행-systemd)
* [MQTT 데이터 구조](#-mqtt-데이터-전송-구조)

---

## ✅ 사전 요구사항

* Raspberry Pi OS (Bookworm or 최신 버전)
* I2C, GPIO, UART 인터페이스 활성화
* Python 3.11 이상

---

## 🚀 빠른 실행
```bash
git clone <repo-url>
cd ssafy_project
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

> 상세 설치는 [설치 및 환경 구성](#-설치-및-환경-구성) 참고

---

## 📦 설치 및 환경 구성

### 1. 필수 패키지 설치

```bash
sudo apt update
sudo apt install python3-rpi.gpio python3-serial python3-smbus i2c-tools
```

### 2. 프로젝트 디렉토리 생성 및 구조

```bash
mkdir ~/ssafy_project
cd ~/ssafy_project
mkdir sensor_project scripts
```

```
ssafy_project/
├── .venv/                      # Python 가상환경
├── scripts/                    # 백업 및 의존성 관리 스크립트
│   ├── backup.sh
│   ├── freeze_deps.sh
│   └── restore.sh
├── sensor_project/
│   └── src/
│       ├── sensor/
│       │   ├── BME280.py        # BME280 온습도/기압 센서 제어 모듈
│       │   ├── SHT41.py         # SHT41 온습도 센서 제어 모듈
│       │   ├── SHTC3.py         # SHTC3 온습도 센서 제어 모듈 (PCA9548A 멀티플렉서 사용)
│       │   ├── GP2Y1010AU0F.py  # 미세먼지 센서 제어 모듈 (ADS1115 ADC 사용)
│       │   ├── ADS1115.py       # ADS1115 ADC 모듈 제어
│       │   ├── MH-Z19B.py       # CO₂ 센서 제어 모듈 (UART)
│       ├── config.py            # 센서 설정값, MQTT 브로커 주소 등 환경설정
│       ├── mqtt_client.py       # MQTT 발행/구독 로직
│       ├── main.py              # 센서 데이터 수집 + MQTT 전송 메인 실행 파일
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### 3. 가상환경 생성 및 활성화

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
```
※ `--system-site-packages` 옵션은 system Python의 GPIO/I2C 라이브러리에 접근하기 위함입니다.

### 4. pip 업그레이드 및 필수 라이브러리 설치

```bash
pip install --upgrade pip setuptools wheel
pip install adafruit-blinka adafruit-circuitpython-bme280 adafruit-circuitpython-sht4x adafruit-circuitpython-ads1x15 paho-mqtt
# BME280 (온습도 + 기압) SHT41 (고정밀 온습도) ADS1115 (아날로그 → 디지털) MQTT 통신
```

### 5. 가상환경에서 시스템 GPIO/I2C 접근 설정

```bash
cd .venv/lib/python3.11/site-packages
# RPi.GPIO 심볼릭 링크 생성
ln -s /usr/lib/python3.11/dist-packages/RPi .
# smbus2 (I2C) 링크 생성
ln -s /usr/lib/python3.11/dist-packages/smbus* .
# (필요 시) serial 링크 생성
ln -s /usr/lib/python3.11/dist-packages/serial* .
```

---

### 🧪 테스트 스크립트 (test_imports.py)
센서 모듈 및 GPIO 관련 패키지들이 정상적으로 설치되었는지 확인합니다.
`~/ssafy_project/sensor_project/test_imports.py` 생성 후 아래 내용 입력:
```python
# test_imports.py
import RPi.GPIO as GPIO
import smbus2
import serial
import board
import busio

print("✅ All modules imported successfully!")
```
### 실행 :
```bash
cd ~/ssafy_project/sensor_project
python test_imports.py
```
> ✅ All modules imported successfully!
> 이 출력이 보이면 모든 의존성 설치가 완료된 것입니다.

---

### 🔒 주의사항
- GPIO는 root 권한이 필요하지 않지만, I2C 및 Serial 포트 접근 권한은 pi 계정이 속한 그룹에 따라 다를 수 있습니다.
- `sudo raspi-config` → Interface Options → I2C, Serial, GPIO 활성화 필요
- `.venv` 내부에서 GPIO 접근을 위해 반드시 `--system-site-packages` 옵션이 포함되어야 하며, 위의 심볼릭 링크를 설정해야 합니다.

---

## UART 문제 해결

### 🛠 /dev/serial0이 /dev/ttyAMA0이 아니고 /dev/ttyAMA10으로 설정되는 문제 해결
라즈베리파이 5에서 UART를 사용할 때, /dev/serial0이 ttyAMA10으로 매핑되어 UART 통신이 정상적으로 동작하지 않는 경우가 있습니다. 이는 내부 udev 규칙에 의해 /dev/serial0 → ttyAMA10으로 자동 지정되는 문제이며, 아래 과정을 따라 해결할 수 있습니다.

---

#### ✅ 현재 상태 확인
```bash
ls -l /dev/serial*
```
출력 예시:
```bash
/dev/serial0 -> ttyAMA10
```
위와 같이 나온다면, 아래 과정을 따라 고정 설정합니다.

---

#### 🔧 1. /boot/firmware/config.txt 설정
```bash
sudo nano /boot/firmware/config.txt
```
아래 항목들을 [all] 블록에 반드시 포함시키세요:
```ini
enable_uart=1
dtoverlay=disable-bt
dtoverlay=uart0
```

---

#### 🔧 2. /boot/firmware/cmdline.txt 확인
```bash
cat /boot/firmware/cmdline.txt
```
console=ttyAMA10 또는 serial0 관련 설정이 있다면 제거하거나 tty1만 남기세요:
```txt
console=tty1 ...
```

---

#### 🔥 핵심 원인: udev rules에서 serial0 → ttyAMA10이 강제됨
시스템 udev 규칙 중 일부는 내부적으로 /dev/serial0을 ttyAMA10 등으로 연결하려고 시도할 수 있습니다.

해당 규칙 예시:
```udev
KERNEL=="ttyAMA[0-9]", KERNELS=="serial0", SYMLINK+="serial2"
```

---

#### 🛠 해결 방법 (추천): 수동으로 serial0 → ttyAMA0 고정
1. 아래 명령으로 udev 규칙 파일을 생성합니다:
```bash
sudo nano /etc/udev/rules.d/99-serial0-fix.rules
```
2. 다음 한 줄을 추가합니다:
```udev
KERNEL=="ttyAMA0", SYMLINK+="serial0"
```
3. 규칙 적용:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```
또는 재부팅:
```bash
sudo reboot
```
4. 이후 다시 확인:
```bash
ls -l /dev/serial*
```
정상 출력:
```bash
/dev/serial0 -> ttyAMA0
```

---

#### 🧪 UART 통신 테스트 (TX ↔ RX Loopback)
1. GPIO 14 (TX, physical pin 8)과 GPIO 15 (RX, pin 10)을 점퍼 와이어로 직접 연결합니다.
2. 다음 테스트 스크립트 실행:
```python
# uart_test.py
import serial, time
ser = serial.Serial("/dev/serial0", baudrate=115200, timeout=1)
ser.write(b"Hello from Pi!\n")
time.sleep(0.1)
print("수신된 메시지:", ser.readline().decode(errors="ignore").strip())
ser.close()
```
3. 출력 예시:
```csharp
수신된 메시지: Hello from Pi!
```
이 메시지가 출력되면 UART 설정 및 GPIO 핀 연결이 정상입니다.

---

📌 참고
| 기능         | 사용 GPIO 핀                | 설명                   |
| ---------- | ------------------------ | -------------------- |
| **UART**   | GPIO14 (TX), GPIO15 (RX) | `/dev/serial0`로 통신   |
| **I2C**    | GPIO2 (SDA), GPIO3 (SCL) | I2C 센서용 (기본 I2C1 버스) |
| **SPI**    | GPIO7\~GPIO11            | SPI 장치 연결용           |
| **1-Wire** | GPIO4                    | DS18B20 등 온도센서 전용    |


> 이 설정은 UART만 변경하며, 다른 GPIO 기능이나 I2C/SPI/1-Wire에는 영향을 주지 않습니다.

---

## 📡 센서 목록 및 기능

| 센서명              | 파일명               | 기능 설명                        | 연결 방식                              |
| ---------------- | ----------------- | ---------------------------- | ---------------------------------- |
| **BME280**       | `BME280.py`       | 온도, 습도, 기압 측정                | I2C (SDA=GPIO 2, SCL=GPIO 3, 3.3V) |
| **SHT41**        | `SHT41.py`        | 고정밀 온습도 측정                   | I2C, PCA9548A CH1 (3.3V)           |
| **SHTC3 x4**     | `SHTC3.py`        | 온습도 측정, PCA9548A CH2\~CH5 연결 | I2C (3.3V)                         |
| **ADS1115**      | `ADS1115.py`      | 아날로그 → 디지털 변환 (미세먼지 센서 연결)   | I2C (3.3V)                         |
| **GP2Y1010AU0F** | `GP2Y1010AU0F.py` | 미세먼지 농도 측정 (PWM + ADC)       | PWM=GPIO 18, ADC=ADS1115 A0, 5V    |
| **MH-Z19B**      | `MH-Z19B.py`      | CO₂ 농도 측정 (온도 포함)            | UART (TX=GPIO 14, RX=GPIO 15, 5V)  |

---

## 🔌 하드웨어 연결 (라즈베리파이 기준)

**왼쪽 (3.3V 전원 계열)**

* 3.3V → PCA9548A, ADS1115, BME280, SHT41, SHTC3 (4개)
* GPIO 2 (SDA) → PCA9548A & ADS1115 & BME280 SDA
* GPIO 3 (SCL) → PCA9548A & ADS1115 & BME280 SCL

**오른쪽 (5V 전원 계열)**

* 5V → GP2Y1010AU0F, MH-Z19B
* GND → 모든 센서 공통
* GPIO 14 (TX) → MH-Z19B RX
* GPIO 15 (RX) → MH-Z19B TX
* GPIO 18 (PWM) → GP2Y1010AU0F LED 제어

---

## 🔌 PCA9548A & ADS1115 하드웨어 연결 상세

### **PCA9548A (I2C 멀티플렉서)**

* **주소 설정**:

  * A2 → **HIGH** (3.3V)
  * A1, A0 → 필요 시 LOW 또는 HIGH로 변경 가능 (본 프로젝트에서는 기본 LOW)
  * 이 설정으로 I2C 주소는 **0x74**

* **전원 및 I2C 연결 (라즈베리파이 5)**

  * **VCC** → 3.3V (Physical pin 1)
  * **GND** → GND (Physical pin 9)
  * **SDA** → GPIO 2 (Physical pin 3)
  * **SCL** → GPIO 3 (Physical pin 5)

* **채널별 센서 연결**:

  * CH1: SHT41
  * CH2\~CH5: SHTC3 (각 채널별 1개 센서)

---

### **ADS1115 (16-bit ADC)**

* **I2C 연결 (라즈베리파이 5)**

  * **VDD** → 3.3V (Physical pin 1)
  * **GND** → GND (Physical pin 9)
  * **SDA** → GPIO 2 (Physical pin 3)
  * **SCL** → GPIO 3 (Physical pin 5)

* **센서 입력 연결**

  * **A0** → GP2Y1010AU0F 미세먼지 센서의 **Analog Out 핀**
  * A1\~A3 → 미사용 (필요 시 다른 아날로그 센서 연결 가능)

* **기타**

  * ADDR/ALERT/RDY 핀은 미사용

---

## BME280 연결 다이어그램

**BME280 (온습도 + 기압 센서)**

* **VCC** → 3.3V (Physical pin 1)
* **GND** → GND (Physical pin 9)
* **SDA** → GPIO 2 (Physical pin 3)
* **SCL** → GPIO 3 (Physical pin 5)

📌 **특징**

* I2C 주소: 0x76 또는 0x77 (보드 납땜 상태에 따라 결정)
* PCA9548A 없이 **직접** I2C1 버스에 연결됨

---

## MH-Z19B 연결 다이어그램

**MH-Z19B (CO₂ 센서)**

* **Vin** → 5V (Physical pin 2)
* **GND** → GND (Physical pin 6)
* **TX (센서)** → GPIO 15 (RX, Physical pin 10)
* **RX (센서)** → GPIO 14 (TX, Physical pin 8)

📌 **특징**

* UART 통신 (/dev/serial0)
* 기본 보레이트: 9600bps
* 5V 전원 구동

---

### 전체 연결 개요

```
Raspberry Pi 5
├── I2C1 (GPIO2=SDA, GPIO3=SCL)
│   ├── PCA9548A (주소: 0x74)
│   │   ├── CH1 → SHT41
│   │   ├── CH2~CH5 → SHTC3 x4
│   ├── ADS1115 (주소: 0x48)
│   │   └── A0 ← GP2Y1010AU0F (Analog Out)
│   └── BME280 (주소: 0x76/0x77)
└── UART (/dev/serial0)
    └── MH-Z19B (TX/RX)
```

---

### 🔌 PCA9548A & ADS1115 하드웨어 연결 다이어그램

```plaintext
[Raspberry Pi 5 - GPIO Header]                          [PCA9548A]                          [SHT Sensors]
+-------------------------------+              +-------------------+                  +----------------------+
| 3.3V (Pin 1) -----------------+--------------> VCC                |                  | CH1 -> SHT41         |
| GND (Pin 9) ------------------+--------------> GND                |                  | CH2 -> SHTC3         |
| GPIO 2 (SDA, Pin 3) ----------+--------------> SDA                |                  | CH3 -> SHTC3         |
| GPIO 3 (SCL, Pin 5) ----------+--------------> SCL                |                  | CH4 -> SHTC3         |
|                               |              | A2 -> HIGH (3.3V)  |                  | CH5 -> SHTC3         |
|                               |              +-------------------+                  +----------------------+
|                               |
|                               |              [ADS1115]                             [GP2Y1010AU0F]
|                               |              +-------------------+                  +----------------------+
| 3.3V (Pin 1) -----------------+--------------> VDD                |                  | VCC -> 5V (Pin 2)    |
| GND (Pin 9) ------------------+--------------> GND                |                  | GND -> GND (Pin 6)   |
| GPIO 2 (SDA, Pin 3) ----------+--------------> SDA                |                  | PWM -> GPIO 18 (Pin 12)
| GPIO 3 (SCL, Pin 5) ----------+--------------> SCL                |                  | Analog Out -> A0 ----+
|                               |              | A0  <--------------+------------------+
|                               |              +-------------------+
+-------------------------------+
```

📌 **주의 사항**

* PCA9548A와 ADS1115 모두 **3.3V 전원**을 사용 (5V 연결 금지)
* I2C 라인은 **병렬 연결** 가능하지만, PCA9548A에 연결된 센서는 채널 전환 후 개별 접근 필요
* GP2Y1010AU0F의 **Analog Out**은 반드시 ADS1115 A0을 통해 읽어야 하며, 직접 라즈베리파이 GPIO로 연결 불가

---

## 💾 백업 및 복원

```bash
# 현재 소스/환경 백업
./scripts/backup.sh

# 현재 가상환경 의존성 저장
./scripts/freeze_deps.sh

# 백업 복원
./scripts/restore.sh
```

---

## 📈 실행 로그 예시

```plaintext
Pub status/hvac/1/all (QoS=0): {"hvac_id": 1, "timestamp": "2025-08-15T12:00:00+09:00", ...}
```

---

## 🔒 자동 실행 (systemd)

```bash
sudo nano /etc/systemd/system/sensor.service
```

```ini
[Unit]
Description=Sensor Data Collector
After=network.target

[Service]
ExecStart=/home/pi/ssafy_project/.venv/bin/python -m src.main
WorkingDirectory=/home/pi/ssafy_project/sensor_project
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor.service
sudo systemctl start sensor.service
```

---

## 📤 MQTT 데이터 전송 구조

* **발행 주기**

  * SHTC3 (4개): 채널 순차 읽기, 전체 주기 약 2초
  * MH-Z19B: 5초마다 1회 읽기
  * BME280, SHT41, GP2Y1010AU0F: 1\~2초 간격
  * 모든 센서 값은 5초 주기로 MQTT 발행

* **토픽 구조**

```
status/hvac/1/all
```

* **메시지 예시 (JSON)**

```json
{
  "hvac_id": 1,
  "timestamp": "2025-08-15T12:00:00+09:00",
  "bme280": {"temp": 25.1, "hum": 44.2, "press": 1013.2},
  "sht41": {"temp": 25.0, "hum": 44.0},
  "shtc3": [
    {"temp": 24.9, "hum": 44.1},
    {"temp": 25.0, "hum": 44.3},
    {"temp": 25.2, "hum": 44.0},
    {"temp": 24.8, "hum": 44.2}
  ],
  "co2": 420,
  "pm25": 18
}
```

---

## 📝 MQTT 클라이언트 (`mqtt_client.py`)

* Paho MQTT 사용 (`pip install paho-mqtt`)
* `publish(topic, payload)` 방식으로 JSON 데이터 송신
* 브로커 주소, 포트, 토픽은 `config.py`에서 관리

---

## 🚀 메인 실행 (`main.py`)

* 모든 센서 모듈을 불러와 주기적으로 측정
* 스레드/비동기 방식으로 각 센서 읽기 간격 최적화
* MQTT 발행 스케줄러 포함

**실행 방법:**

```bash
cd ~/ssafy_project
source .venv/bin/activate
python -m src.main
```

---

## 🔒 주의사항

* I2C 주소 충돌 방지를 위해 PCA9548A 사용
* 5V 센서와 3.3V 센서 전원 분리로 전원 안정성 확보
* `.env`에 MQTT 브로커 정보 저장 (Git에 업로드 금지)

---

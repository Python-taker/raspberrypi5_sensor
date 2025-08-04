# SSAFY Sensor Project (Raspberry Pi 5 기준)

본 프로젝트는 Raspberry Pi 5 기반에서 `.venv` 가상환경을 사용하여 다양한 센서(BME280, SHT41, GP2Y1010AU0F 등)를 제어하기 위한 설정 및 테스트 가이드를 제공합니다.

---

## ✅ 사전 요구사항

- Raspberry Pi OS (Bookworm or 최신 버전)
- I2C, GPIO 인터페이스 활성화
- Python 3.11 이상

---

## 📦 설치 및 환경 구성

### 1. GPIO 시스템 패키지 설치

```bash
sudo apt update
sudo apt install python3-rpi.gpio
```

### 2. 프로젝트 디렉토리 생성
```bash
mkdir ~/ssafy_project
cd ~/ssafy_project
mkdir sensor_project
```

### 3. 가상환경 생성 및 활성화
```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
```
※ `--system-site-packages` 옵션은 system Python의 GPIO/I2C 라이브러리에 접근하기 위함입니다.

---

### 4. pip 업그레이드 및 필수 도구 설치
```bash
pip install --upgrade pip setuptools wheel
```

---

### 5. Adafruit Blinka 및 센서 드라이버 설치
```bash
# GPIO/I2C abstraction 라이브러리
pip install adafruit-blinka

# 필요한 센서 드라이버만 선택적으로 설치
pip install adafruit-circuitpython-bme280       # BME280 (온습도 + 기압)
pip install adafruit-circuitpython-sht4x        # SHT41 (고정밀 온습도)
pip install adafruit-circuitpython-ads1x15      # ADS1115 (아날로그 → 디지털)
```

---

### 6. 가상환경에서도 시스템 GPIO 라이브러리 사용 설정
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

### 📁 폴더 구조
```bash
ssafy_project/
├── .venv/                        # 가상환경
├── README.md                     # 이 문서
├── requirements.txt              #
└── sensor_project/              
    └── test_imports.py          # 의존성 테스트 스크립트
```

---

### 🔒 주의사항
- GPIO는 root 권한이 필요하지 않지만, I2C 및 Serial 포트 접근 권한은 pi 계정이 속한 그룹에 따라 다를 수 있습니다.
- `sudo raspi-config` → Interface Options → I2C, Serial, GPIO 활성화 필요
- `.venv` 내부에서 GPIO 접근을 위해 반드시 `--system-site-packages` 옵션이 포함되어야 하며, 위의 심볼릭 링크를 설정해야 합니다.

---

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

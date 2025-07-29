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
" ✅ All modules imported successfully!
이 출력이 보이면 모든 의존성 설치가 완료된 것입니다.

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

### ✅ 다음 단계
센서별 테스트 스크립트 또는 통합 센서 읽기 모듈을 작성하여 센서 데이터를 수집할 수 있습니다.
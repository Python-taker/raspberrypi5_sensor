import serial
import time

ser = serial.Serial("/dev/serial0", baudrate=115200, timeout=1)

test_message = b"Hello from Pi!\n"
ser.write(test_message)
time.sleep(0.1)  # 데이터 전송 대기

response = ser.readline()
print("수신된 메시지:", response.decode(errors="ignore").strip())

ser.close()

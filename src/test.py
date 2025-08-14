import paho.mqtt.client as mqtt

BROKER_HOST = "192.168.100.108"   # 브로커 IP 또는 도메인 (예: "192.168.0.10")
BROKER_PORT = 1883          # 브로커 포트 (보통 1883)
TOPIC = "sensor/all"        # 구독할 토픽

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(TOPIC)
    print(f"Subscribed to topic: {TOPIC}")

def on_message(client, userdata, msg):
    print(f"[RECV] Topic: {msg.topic} | Payload: {msg.payload.decode()}")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, 60)
    print(f"Connecting to MQTT broker {BROKER_HOST}:{BROKER_PORT} ...")

    client.loop_forever()

if __name__ == "__main__":
    main()

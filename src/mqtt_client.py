import paho.mqtt.client as mqtt

class MQTTClient:
    def __init__(self, broker_host, broker_port, publish_topics):
        self.client = mqtt.Client()
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.publish_topics = publish_topics if publish_topics else []

    def connect(self):
        self.client.connect(self.broker_host, self.broker_port)
        self.client.loop_start()

    def publish(self, topic, payload, qos=0):
        if topic in [t[0] for t in self.publish_topics]:
            print(f"Pub {topic} (QoS={qos}): {payload}")
            self.client.publish(topic, payload, qos=qos)
        else:
            print(f"[Warning] {topic} is not in publish_topics list. Publishing anyway.")
            self.client.publish(topic, payload, qos=qos)

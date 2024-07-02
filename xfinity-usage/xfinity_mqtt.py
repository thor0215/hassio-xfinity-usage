# python 3.11

import random
import time
import os
import logging
from tenacity import stop_after_attempt,  wait_exponential, retry, before_sleep_log

from paho.mqtt import client as mqtt

class XfinityMqtt ():

    def __init__(self, max_retries=5, retry_delay=5):
        self.broker = 'core-mosquitto'
        self.port = 1883
        self.topic = "xfinity_usage"
        # Generate a Client ID with the publish prefix.
        self.client_id = f'publish-{random.randint(0, 1000)}'
        self.client = mqtt.Client(self.client_id,
                            clean_session=True)
        self.client.on_connect = self.on_connect
        self.retain = True   # Retain MQTT messages
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if os.getenv('MQTT_SERVICE') and os.getenv('MQTT_HOST') and os.getenv('MQTT_PORT'):
            self.broker = os.getenv('MQTT_HOST')
            self.port = int(os.getenv('MQTT_PORT')) if os.getenv('MQTT_PORT') else 1883
            if os.getenv('MQTT_USERNAME') and os.getenv('MQTT_PASSWORD'):
                self.mqtt_username = os.getenv('MQTT_USERNAME')
                self.mqtt_password = os.getenv('MQTT_PASSWORD')
                self.mqtt_auth = True
                self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        else:
            logging.error("No MQTT configuration specified")
            exit(98)
    

    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', level="INFO", datefmt='%Y-%m-%dT%H:%M:%S')
    logger = logging.getLogger(__name__)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info(f"Connected to MQTT Broker!")
        else:
            logging.error(f"MQTT Failed to connect, {mqtt.error_string(rc)}")
            #raise ConnectionError(f"MQTT Error: {mqtt.error_string(rc)}")

    def connect_mqtt(self) -> None:
        if self.connect_with_retry():
            return self.client

    def connect_with_retry(self):
        retries = 0
        while retries < self.max_retries:
            try:
                self.client.connect(self.broker, self.port)
                self.client.loop_start()
                return True
            except Exception as e:
                logging.error(f"Connection attempt {retries + 1} failed: {e}")
                retries += 1
                if retries < self.max_retries:
                    logging.error(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        print("Max retries reached. Could not connect to MQTT broker.")
        return False

    def disconnect_mqtt(self) -> None:
        self.client.disconnect()


    def publish(self,payload) -> None:
        result = self.client.publish(self.topic, payload, 0, self.retain)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logging.info(f"Updating MQTT topic `{self.topic}`")
            logging.debug(f"Send `{payload}` to topic `{self.topic}`")
        else:
            logging.error(f"Failed to send message to topic {self.topic}")


    def run(self) -> None:
            self.client = self.connect_mqtt()
            self.client.reconnect_delay_set(1,15)
            if self.client.is_connected():
                self.publish('{"attributes": {"policy_name": "1.2 Terabyte Data Plan", "start_date": "07/01/2024", "end_date": "07/31/2024", "home_usage": 37, "wifi_usage": 0, "total_usage": 37, "allowable_usage": 1229, "unit_of_measure": "GB", "display_usage": true, "devices": [{"id": "44:A5:6E:B9:E3:60", "usage": 42, "policyName": "XI Superfast"}], "additional_blocks_used": 0, "additional_cost_per_block": 10, "additional_units_per_block": 50, "additional_block_size": 50, "additional_included": 0, "additional_used": 0, "additional_percent_used": 0.0, "additional_remaining": 0, "billable_overage": 0, "overage_charges": 0.0, "overage_used": 0, "current_credit_amount": 0, "max_credit_amount": 0, "maximum_overage_charge": 100, "policy": "limited", "courtesy_used": 0, "courtesy_remaining": 1, "courtesy_allowed": 1, "courtesy_months": ["03/2023"], "in_paid_overage": false, "remaining_usage": 1192, "friendly_name": "Xfinity Usage", "unit_of_measurement": "GB", "device_class": "data_size", "state_class": "measurement", "icon": "mdi:network", "internet_download_speeds_Mbps": 800, "internet_upload_speeds_Mbps": 20}, "state": 37}')
            else:
                self.client.reconnect()
            
            self.disconnect_mqtt()


if __name__ == '__main__':
    mqtt_client = XfinityMqtt()
    mqtt_client.run()
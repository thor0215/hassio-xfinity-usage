import json
import random
import socket
import ssl
from paho.mqtt import client as mqtt
from xfinity_helper import *


class XfinityMqtt ():

    def __init__(self, max_retries=5, retry_delay=5):
        self.broker = 'core-mosquitto'
        self.port = 1883
        self.tls = False
        self.topic = "xfinity_usage"
        # Generate a Client ID with the publish prefix.
        self.client_id = f'publish-{random.randint(0, 1000)}'
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,self.client_id,
                            clean_session=True)
        self.client.enable_logger(logger)
        self.client.on_connect = self.on_connect
        self.retain = True   # Retain MQTT messages
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.mqtt_device_details_dict = {}

        self.mqtt_json_raw_usage = None
        self.mqtt_state = int
        self.mqtt_json_attributes_dict = dict
        self.mqtt_device_config_dict = {
            "device_class": "data_size",
            "unit_of_measurement": "GB",
            "state_class": "measurement",
            "state_topic": "homeassistant/sensor/xfinity_internet/state",
            "name": "Internet Usage",
            "unique_id": "internet_usage",
            "icon": "mdi:wan",
            "device": {
                "identifiers": [
                ""
                ],
                "name": "Xfinity Internet",
                "model": "",
                "manufacturer": "Xfinity"
            },
            "json_attributes_topic": "homeassistant/sensor/xfinity_internet/attributes"
        }

        if MQTT_SERVICE:
            self.broker = MQTT_HOST
            self.port = MQTT_PORT
            if MQTT_USERNAME is not None and MQTT_PASSWORD is not None:
                self.mqtt_username = MQTT_USERNAME
                self.mqtt_password = MQTT_PASSWORD
                self.mqtt_auth = True
                self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        else:
            logger.error("No MQTT configuration specified")
            exit(exit_code.MISSING_MQTT_CONFIG.value)

        self.client = self.connect_mqtt()

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            if self.tls:
                logger.info(f"Connected to MQTT Broker using TLS!")
            else:
                logger.info(f"Connected to MQTT Broker!")
        else:
            logger.error(f"MQTT Failed to connect, {mqtt.error_string(rc)}")

    def is_connected_mqtt(self) -> None:
        return self.client.is_connected()

    def connect_mqtt(self) -> None:
        try:
            context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            if context.wrap_socket(socket.create_connection((self.broker, self.port)),
                                        server_hostname=self.broker):
                self.tls = True
                self.client.tls_set()
                self.client.tls_insecure_set(True)
        except Exception as exception:
            if exception.errno == 104:
                self.tls = False
        finally: 
            try:
                self.client.connect(self.broker, self.port)
                self.client.loop_start()
                return self.client
            except Exception as exception:
                logger.error(f"MQTT Failed to connect, [{exception.errno}] {exception.strerror}")

    def disconnect_mqtt(self) -> None:
        self.client.disconnect()

    def publish_mqtt(self,usage_payload) -> None:
        """
        homeassistant/sensor/xfinity_internet_usage/config
        {
        "device_class": "data_size",
        "unit_of_measurement": "Mbit/s",
        "state_class": "measurement",
        "state_topic": "homeassistant/sensor/xfinity_internet/state",
        "name": "Xfinity Internet Usage",
        "unique_id": "xfinity_internet_usage",
        "device": {
            "identifiers": [
            "44:A5:6E:B9:E3:60"
            ],
            "name": "Xfinity Internet Usage",
            "model": "XI Superfast",
            "manufacturer": "Xfinity",
            "sw_version": "2024.07"
        },
        "json_attributes_topic": "homeassistant/sensor/xfinity_internet/attributes"
        }

        """
        logger.debug(f"MQTT Device Config:\n {json.dumps(self.mqtt_device_config_dict)}")
        
        topic = 'homeassistant/sensor/xfinity_internet/config'
        payload = json.dumps(self.mqtt_device_config_dict)
        result = self.client.publish(topic, payload, 0, self.retain)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logger.info(f"Updating MQTT topic `{topic}`")
            logger.debug(f"Send `{payload}` to topic `{topic}`")
        else:
            logger.error(f"Failed to send message to topic {topic}")

        topic = 'homeassistant/sensor/xfinity_internet/state'
        payload = self.mqtt_state
        result = self.client.publish(topic, payload, 0, self.retain)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logger.info(f"Updating MQTT topic `{topic}`")
            logger.debug(f"Send `{payload}` to topic `{topic}`")
        else:
            logger.error(f"Failed to send message to topic {topic}")

        topic = 'homeassistant/sensor/xfinity_internet/attributes'
        payload = json.dumps(self.mqtt_json_attributes_dict)
        result = self.client.publish(topic, payload, 0, self.retain)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logger.info(f"Updating MQTT topic `{topic}`")
            logger.debug(f"Send `{payload}` to topic `{topic}`")
        else:
            logger.error(f"Failed to send message to topic {topic}")

        if  MQTT_RAW_USAGE and \
            self.mqtt_json_raw_usage is not None:
                topic = 'xfinity'
                payload = json.dumps(self.mqtt_json_raw_usage)
                result = self.client.publish(topic, payload, 0, self.retain)
                # result: [0, 1]
                status = result[0]
                if status == 0:
                    logger.info(f"Updating MQTT topic `{topic}`")
                    logger.debug(f"Send `{payload}` to topic `{topic}`")
                else:
                    logger.error(f"Failed to send message to topic {topic}")

    def set_mqtt_device_details(self, _raw_device_details: dict) -> None:
        """
        "deviceDetails": {
            "mac": "44:A5:6E:B9:E3:60",
            "serialNumber": "44A56EB9E360",
            "model": "cm1000v2",
            "make": "NETGEAR",
            "platform": "CM",
            "type": "Cable Modem",
            "hasCableModem": true,
            "lineOfBusiness": "INTERNET"
            }
        """
        # MQTT Home Assistant Device Config
        self.mqtt_device_config_dict['device']['identifiers'] = _raw_device_details.get('macAddress', '00:00:00:00:00')
        self.mqtt_device_config_dict['device']['model'] = _raw_device_details.get('model', 'xFinity') or 'unknown'
        self.mqtt_device_config_dict['device']['manufacturer'] = _raw_device_details.get('make', 'xFi Gateway') or 'unknown'
        self.mqtt_device_config_dict['device']['name'] = "Xfinity"

    def set_mqtt_state(self, _raw_usage_details: dict) -> None:
        self.mqtt_state = _raw_usage_details['state']

    def set_mqtt_json_attributes(self, _raw_usage_details: dict) -> None:
        self.mqtt_json_attributes_dict = _raw_usage_details['attributes']

    def set_mqtt_raw_usage(self, _raw_usage_details: dict) -> None:
        self.mqtt_json_raw_usage = _raw_usage_details
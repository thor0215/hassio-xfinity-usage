import pytest
import os
import socket
from unittest.mock import MagicMock, patch
from xfinity_usage.xfinity_mqtt import XfinityMqtt, is_mqtt_available

@pytest.fixture
def mock_mqtt_client():
    with patch('xfinity_usage.xfinity_mqtt.mqtt.Client') as mock_client:
        yield mock_client

@pytest.fixture
@patch("xfinity_usage.xfinity_mqtt._MQTT_SERVICE", True)
def mqtt_instance(mock_mqtt_client):
    os.environ['MQTT_SERVICE'] = 'true'
    mqtt = XfinityMqtt()
    return mqtt

@patch("xfinity_usage.xfinity_mqtt._MQTT_SERVICE", True)
def test_is_mqtt_available():
    assert is_mqtt_available() is True

def test_is_mqtt_not_available():
    assert is_mqtt_available() is False

def test_set_mqtt_device_details(mqtt_instance):
    device_details = {
        'macAddress': '00:11:22:33:44:55',
        'model': 'test_model',
        'make': 'test_make'
    }
    mqtt_instance.set_mqtt_device_details(device_details)
    
    assert mqtt_instance.mqtt_device_config_dict['device']['identifiers'] == '00:11:22:33:44:55'
    assert mqtt_instance.mqtt_device_config_dict['device']['model'] == 'test_model'
    assert mqtt_instance.mqtt_device_config_dict['device']['manufacturer'] == 'test_make'

def test_set_mqtt_state(mqtt_instance):
    usage_details = {'state': 100}
    mqtt_instance.set_mqtt_state(usage_details)
    assert mqtt_instance.mqtt_state == 100

def test_set_mqtt_json_attributes(mqtt_instance):
    attributes = {'attributes': {'test_key': 'test_value'}}
    mqtt_instance.set_mqtt_json_attributes(attributes)
    assert mqtt_instance.mqtt_json_attributes_dict == {'test_key': 'test_value'}

def test_set_mqtt_raw_usage(mqtt_instance):
    raw_usage = {'data': 'test_data'}
    mqtt_instance.set_mqtt_raw_usage(raw_usage)
    assert mqtt_instance.mqtt_json_raw_usage == {'data': 'test_data'}

def test_disconnect_mqtt(mqtt_instance):
    mqtt_instance.disconnect_mqtt()
    mqtt_instance.client.disconnect.assert_called_once()

@patch("xfinity_usage.xfinity_mqtt._MQTT_SERVICE", True)
def test_mqtt_auth_credentials():
    os.environ['MQTT_USERNAME'] = 'test_user'
    os.environ['MQTT_PASSWORD'] = 'test_pass'
    
    with patch('xfinity_usage.xfinity_mqtt.mqtt.Client') as mock_client:
        mqtt = XfinityMqtt()
        mock_client.return_value.username_pw_set.assert_called_once_with('test_user', 'test_pass')


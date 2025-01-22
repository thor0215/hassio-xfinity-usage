import os
import json
from enum import Enum

class exit_code(Enum):
    SUCCESS = 0
    MISSING_LOGIN_CONFIG = 80
    MISSING_MQTT_CONFIG = 81
    TOKEN_CODE = 91
    BAD_AUTHENTICATION = 93
    MAIN_EXCEPTION = 98


# GLOBAL URLS
OAUTH_AUTHORIZE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/authorize'
OAUTH_CODE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code'
OAUTH_TOKEN_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/token'
OAUTH_JWKS_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/keys/jwks'
GRAPHQL_URL = 'https://gw.api.dh.comcast.com/galileo/graphql'


# Xfinity authentication
XFINITY_CODE = os.environ.get('XFINITY_CODE', None)
XFINITY_CODE_PLACEHOLDER = 'Example Code 251774815a2140a5abf64fa740dabf0c'


# Script polling rate
BYPASS = int(os.environ.get('BYPASS',0))
POLLING_RATE = float(os.environ.get('POLLING_RATE', 300.0))


# Playwright timeout
PAGE_TIMEOUT = int(os.environ.get('PAGE_TIMEOUT', 60))

# MQTT
MQTT_SERVICE = json.loads(os.environ.get('MQTT_SERVICE', 'false').lower()) # Convert MQTT_SERVICE string into boolean
MQTT_HOST = os.environ.get('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', None)
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', None)
MQTT_RAW_USAGE = json.loads(os.environ.get('MQTT_RAW_USAGE', 'false').lower()) # Convert MQTT_RAW_USAGE string into boolean

# Home Assistant API
BASHIO_SUPERVISOR_API = os.environ.get('BASHIO_SUPERVISOR_API', '')
BASHIO_SUPERVISOR_TOKEN = os.environ.get('BASHIO_SUPERVISOR_TOKEN', '')
SENSOR_NAME = "sensor.xfinity_usage"
SENSOR_URL = f"{BASHIO_SUPERVISOR_API}/core/api/states/{SENSOR_NAME}"
SENSOR_BACKUP = '/config/.sensor-backup'
ADDON_RESTART_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/restart"
ADDON_STOP_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/stop"
ADDON_OPTIONS_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options"
ADDON_OPTIONS_VALIDATE_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options/validate"
ADDON_OPTIONS_CONFIG_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options/config"


# Logging 
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
DEBUG_LOGGER_FILE = '/config/xfinity.log'

# Xfinity Mobile API
REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN', None)
CLEAR_TOKEN = json.loads(os.environ.get('CLEAR_TOKEN', 'false').lower()) # Convert CLEAR_TOKEN string into boolean
OAUTH_TOKEN_FILE = '/config/.token.json'
OAUTH_CODE_TOKEN_FILE = '/config/.code.json'
OAUTH_PROXY = json.loads(os.environ.get('OAUTH_PROXY','{}')) or None
OAUTH_CERT_VERIFY = json.loads(os.environ.get('OAUTH_CERT_VERIFY','true').lower()) # Convert OAUTH_CERT_VERIFY string into boolean or none
REQUESTS_TIMEOUT = PAGE_TIMEOUT

if not OAUTH_CERT_VERIFY:
    import urllib3
    urllib3.disable_warnings()





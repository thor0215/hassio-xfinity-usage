import os
import json
from enum import Enum

class exit_code(Enum):
    SUCCESS = 0
    MISSING_LOGIN_CONFIG = 80
    MISSING_MQTT_CONFIG = 81
    BAD_AUTHENTICATION = 93
    TOO_MANY_USERNAME = 94
    TOO_MANY_PASSWORD = 95
    BAD_PASSWORD = 96
    TWO_STEP_VERIFICATION = 97
    MAIN_EXCEPTION = 98
    DEBUG_SUPPORT = 99

# Browser mode
HEADLESS = json.loads(os.environ.get('HEADLESS', 'true').lower()) # Convert HEADLESS string into boolean

# Login slow variables
SLOW_DOWN_MIN = 0.5
SLOW_DOWN_MAX = 1.2
SLOW_DOWN_LOGIN = True

# GLOBAL URLS
OAUTH_AUTHORIZE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/authorize'
OAUTH_CODE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code'
OAUTH_TOKEN_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/token'
OAUTH_JWKS_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/keys/jwks'
GRAPHQL_URL = 'https://gw.api.dh.comcast.com/galileo/graphql'

# Xfinity authentication
XFINITY_USERNAME = os.environ.get('XFINITY_USERNAME', None)
XFINITY_PASSWORD = os.environ.get('XFINITY_PASSWORD', None)


# Script polling rate
BYPASS = int(os.environ.get('BYPASS',0))
POLLING_RATE = float(os.environ.get('POLLING_RATE', 300.0))


# Playwright timeout
PAGE_TIMEOUT = int(os.environ.get('PAGE_TIMEOUT', 60))
#PLAYWRIGHT_PROXY = {'server': 'http://192.168.1.21:8083'}
PLAYWRIGHT_PROXY = {}
PLAYWRIGHT_USER_AGENT = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.260 Mobile Safari/537.36'

# MQTT
MQTT_SERVICE = json.loads(os.environ.get('MQTT_SERVICE', 'false').lower()) # Convert MQTT_SERVICE string into boolean
MQTT_HOST = os.environ.get('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', None)
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', None)
MQTT_RAW_USAGE = json.loads(os.environ.get('MQTT_RAW_USAGE', 'false').lower()) # Convert MQTT_RAW_USAGE string into boolean

BASHIO_SUPERVISOR_API = os.environ.get('BASHIO_SUPERVISOR_API', '')
BASHIO_SUPERVISOR_TOKEN = os.environ.get('BASHIO_SUPERVISOR_TOKEN', '')
HOSTNAME = os.environ.get('HOSTNAME', '')
SENSOR_NAME = "sensor.xfinity_usage"
SENSOR_URL = f"{BASHIO_SUPERVISOR_API}/core/api/states/{SENSOR_NAME}"
SENSOR_BACKUP = '/config/.sensor-backup'
ADDON_RESTART_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/restart"
ADDON_OPTIONS_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options"
ADDON_OPTIONS_VALIDATE_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options/validate"
ADDON_OPTIONS_CONFIG_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options/config"


# Logging 
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
DEBUG_LOGGER_FILE = '/config/xfinity.log'
DEBUG_SUPPORT = json.loads(os.environ.get('DEBUG_SUPPORT', 'false').lower()) # Convert DEBUG_SUPPORT string into boolean
if DEBUG_SUPPORT: LOG_LEVEL = 'DEBUG'

REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN', None)
OAUTH_TOKEN_FILE = '/config/.token.json'
#OAUTH_PROXY = {'http': '192.168.1.21:8083', 'https': '192.168.1.21:8083'}
OAUTH_PROXY = {}
#OAUTH_CERT_VERIFY = False
OAUTH_CERT_VERIFY = True
REQUESTS_TIMEOUT = PAGE_TIMEOUT

OAUTH_USER_AGENT = 'Dalvik/2.1.0 (Linux; U; Android 14; SM-G991B Build/G991BXXUEGXJE)'

OAUTH_TOKEN_EXTRA_HEADERS = {
    'Content-Type':             'application/x-www-form-urlencoded',
    'Accept':                   'application/json',
    'User-Agent':               OAUTH_USER_AGENT,
    'Accept-Encoding':          'gzip'
}
OAUTH_TOKEN_DATA = {
    'active_x1_account_count':  'true',
    'partner_id':               'comcast',
    'mso_partner_hint':         'true',
    'scope':                    'profile',
    'rm_hint':                  'true',
    'client_id':                'xfinity-android-application'
}
GRAPHQL_EXTRA_HEADERS = {
    'accept':                  'multipart/mixed; deferSpec=20220824, application/json',
    'user-agent':              'Digital Home / Samsung SM-G991B / Android 14',
    'client':                  'digital-home-android',
    'client-detail':           'MOBILE;Samsung;SM-G991B;Android 14;v5.41.0',
    'accept-language':         'en-US',
    'content-type':            'application/json'
}

GRAPHQL_GATGEWAY_DETAILS_HEADERS = {
    'x-apollo-operation-id': '34a752659014e11c5617dc4d469941230f2b25dffab3197d5bde752a9ecc5569',
    'x-apollo-operation-name': 'User'
}

GRAPHQL_USAGE_DETAILS_HEADERS = {
    'x-apollo-operation-id': '61994c6016ac8c0ebcca875084919e5e01cb3b116a86aaf9646e597c3a1fbd06',
    'x-apollo-operation-name': 'InternetDataUsage'
}

GRAPHQL_PLAN_DETAILS_HEADERS = {
    'x-apollo-operation-id': 'cb26cdb7288e179b750ec86d62f8a16548902db3d79d2508ca98aa4a8864c7e1',
    'x-apollo-operation-name': 'AccountServicesWithoutXM'
}
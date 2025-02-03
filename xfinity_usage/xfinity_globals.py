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




# HTTP Request timeout
REQUESTS_TIMEOUT = int(os.environ.get('PAGE_TIMEOUT', 60))

# Settings for Web Proxy testing
OAUTH_PROXY = json.loads(os.environ.get('OAUTH_PROXY','{}')) or None
OAUTH_CERT_VERIFY = json.loads(os.environ.get('OAUTH_CERT_VERIFY','true').lower()) # Convert OAUTH_CERT_VERIFY string into boolean or none

if not OAUTH_CERT_VERIFY:
    import urllib3
    urllib3.disable_warnings()





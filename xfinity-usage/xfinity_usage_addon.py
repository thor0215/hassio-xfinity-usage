import os
import json
import logging
import shutil
import requests
import urllib.parse
import fnmatch
import time
import random
import base64
import jwt
import re
import textwrap
import socket
import ssl
from datetime import datetime
from time import sleep
from pathlib import Path
from tenacity import stop_after_attempt,  wait_exponential, retry, before_sleep_log
from playwright.sync_api import Playwright, Route, Response, Request, Frame, Page, sync_playwright, expect
from paho.mqtt import client as mqtt

def get_current_unix_epoch() -> float:
    return time.time()

def ordinal(n):
    s = ('th', 'st', 'nd', 'rd') + ('th',)*10
    v = n%100
    if v > 13:
      return f'{n}{s[v%10]}'
    else:
      return f'{n}{s[v]}'

"""
Playwright sometimes has an uncaught exception.
Restarting Playwright every 12 hrs helps prevent that

/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/utils/debug.js:29
  if (!value) throw new Error(message || 'Assertion error');
                    ^

Error: Assertion error
    at assert (/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/utils/debug.js:29:21)
    at FrameManager.frameAttached (/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/frames.js:104:25)
    at FFPage._onFrameAttached (/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/firefox/ffPage.js:175:30)
    at FFSession.emit (node:events:513:28)
    at /usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/firefox/ffConnection.js:204:41

Node.js v18.16.0
    at /usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/firefox/ffConnection.js:204:41

Node.js v18.16.0

"""

POLLING_RATE = float(os.environ.get('POLLING_RATE', "300.0"))
PAGE_TIMEOUT = int(os.environ.get('PAGE_TIMEOUT', "60"))
LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper().split('_')[0]
SUPPORT = False
if len(os.environ.get('LOGLEVEL', 'INFO').upper().split('_')) > 1 and 'SUPPORT' == os.environ.get('LOGLEVEL', 'INFO').upper().split('_')[1] : SUPPORT = True
SENSOR_BACKUP = '/config/.sensor-backup'
mqtt_client = None

debug_logger_file = '/config/xfinity.log'
profile_paths = ['/config/profile_mobile','/config/profile_linux','/config/profile_win']
FIREFOX_MIN_VERSION = 125
FIREFOX_MAX_VERSION = 129

# Remove browser profile path upon startup
for profile_path in profile_paths:
    if Path(profile_path).exists() and Path(profile_path).is_dir(): shutil.rmtree(profile_path)
# Remove debug log file upon script startup
if os.path.exists(debug_logger_file): os.remove(debug_logger_file)


xfinity_block_list = []
for block_list in os.popen(f"curl -s --connect-timeout {PAGE_TIMEOUT} https://easylist.to/easylist/easyprivacy.txt | grep '^||.*xfinity' | sed -e 's/^||//' -e 's/\^//'"):
    xfinity_block_list.append(block_list.rstrip())

logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(LOGLEVEL)
formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')


if LOGLEVEL == 'DEBUG':
    file_handler = logging.FileHandler(debug_logger_file,mode='w')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler) 
    
    if SUPPORT:
        debug_support_logger = logging.getLogger(__name__ + '.file_logger')
        debug_support_logger.addHandler(file_handler)
        debug_support_logger.propagate = False

    
    for name, value in sorted(os.environ.items()):
        if name == 'XFINITY_PASSWORD':
            value = base64.b64encode(base64.b64encode(value.encode()).decode().strip('=').encode()).decode().strip('=')
        logger.debug(f"{name}: {value}")


def is_mqtt_available() -> bool:
    if os.getenv('MQTT_SERVICE') and os.getenv('MQTT_HOST') and os.getenv('MQTT_PORT'):
        return True
    else:
        return False

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

        if os.getenv('MQTT_SERVICE') and os.getenv('MQTT_HOST') and os.getenv('MQTT_PORT'):
            self.broker = os.getenv('MQTT_HOST')
            self.port = int(os.getenv('MQTT_PORT')) if os.getenv('MQTT_PORT') else 1883
            if os.getenv('MQTT_USERNAME') and os.getenv('MQTT_PASSWORD'):
                self.mqtt_username = os.getenv('MQTT_USERNAME')
                self.mqtt_password = os.getenv('MQTT_PASSWORD')
                self.mqtt_auth = True
                self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        else:
            logger.error("No MQTT configuration specified")
            exit(98)

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
        except Exception as e:
            if e.errno == 104:
                self.tls = False
        finally: 
            try:
                self.client.connect(self.broker, self.port)
                self.client.loop_start()
                return self.client
            except Exception as e:
                logger.error(f"MQTT Failed to connect, [{e.errno}] {e.strerror}")

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

        """
        topic = self.topic
        payload = usage_payload
        result = self.client.publish(topic, payload, 0, self.retain)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logger.info(f"Updating MQTT topic `{topic}`")
            logger.debug(f"Send `{payload}` to topic `{topic}`")
        else:
            logger.error(f"Failed to send message to topic {topic}")
        """


class XfinityUsage ():
    def __init__(self, playwright: Playwright) -> None:
        self.timeout = int(os.environ.get('PAGE_TIMEOUT', "45")) * 1000

        self.POLLING_RATE = float(os.environ.get('POLLING_RATE', "300.0"))

        self.View_Usage_Url = 'https://customer.xfinity.com/#/devices#usage'
        self.View_Wifi_Url = 'https://customer.xfinity.com/settings/wifi'
        self.Internet_Service_Url = 'https://www.xfinity.com/learn/internet-service/auth'
        self.Login_Url = "https://login.xfinity.com/login"
        self.Session_Url = 'https://customer.xfinity.com/apis/session'
        self.Usage_JSON_Url = 'https://api.sc.xfinity.com/session/csp/selfhelp/account/me/services/internet/usage'
        self.Plan_Details_JSON_Url = 'https://api.sc.xfinity.com/session/plan'
        self.Device_Details_Url = 'https://www.xfinity.com/support/status'
        self.Device_Details_JSON_Url = 'https://api.sc.xfinity.com/devices/status'
        self.BASHIO_SUPERVISOR_API = os.environ.get('BASHIO_SUPERVISOR_API', '')
        self.BASHIO_SUPERVISOR_TOKEN = os.environ.get('BASHIO_SUPERVISOR_TOKEN', '')
        self.SENSOR_NAME = "sensor.xfinity_usage"
        self.SENSOR_URL = f"{self.BASHIO_SUPERVISOR_API}/core/api/states/{self.SENSOR_NAME}"

        self.usage_data = None
        self.is_session_active = False
        self.session_details = {}
        self.plan_details_data = None
        self.device_details_data = None
        self.reload_counter = 0
        self.pending_requests = []
        self.slow_down_login = True
        self.FIREFOX_VERSION = str(random.randint(FIREFOX_MIN_VERSION, FIREFOX_MAX_VERSION))


        if SUPPORT: self.support_page_hash = int; self.support_page_screenshot_hash = int

        if os.getenv('XFINITY_PASSWORD') and os.getenv('XFINITY_USERNAME'):
            self.xfinity_username = os.getenv('XFINITY_USERNAME')
            self.xfinity_password = os.getenv('XFINITY_PASSWORD')
        else:
            logger.error("No Username or Password specified")
            exit(99)

        if is_mqtt_available() is False and os.path.isfile(SENSOR_BACKUP) and os.path.getsize(SENSOR_BACKUP):
            with open(SENSOR_BACKUP, 'r') as file:
                self.usage_data = file.read()
                self.update_ha_sensor()

        # Help reduce bot detection
        self.device_choices = []
        self.device_choices.append({
            "user_agent": "Mozilla/5.0 (Android 13; Mobile; rv:"+self.FIREFOX_VERSION+".0) Gecko/"+self.FIREFOX_VERSION+".0 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 414,"height": 896}, "viewport": {"width": 414,"height": 896},
            "device_scale_factor": 2, "is_mobile": True, "has_touch": True
        })
        self.device_choices.append({
            "user_agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:"+self.FIREFOX_VERSION+".0) Gecko/20100101 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 1920,"height": 1080}, "viewport": {"width": 1920,"height": 1080},
            "device_scale_factor": 1, "is_mobile": False, "has_touch": False
        })
        self.device_choices.append({
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:"+self.FIREFOX_VERSION+".0) Gecko/20100101 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 1366,"height": 768}, "viewport": {"width": 1366,"height": 768},
            "device_scale_factor": 2, "is_mobile": False, "has_touch": False
        })


        self.device = random.choice(self.device_choices)
        logger.info(f"Launching {textwrap.shorten(self.device['user_agent'], width=77, placeholder='...')}")
        
        self.firefox_user_prefs={'webgl.disabled': True}
        #self.firefox_user_prefs={'webgl.disabled': False}
        self.webdriver_script = "delete Object.getPrototypeOf(navigator).webdriver"

        #self.browser = playwright.firefox.launch(headless=False,slow_mo=1000,firefox_user_prefs=self.firefox_user_prefs)
        #self.browser = playwright.firefox.launch(headless=True,firefox_user_prefs=self.firefox_user_prefs)
        #self.context = self.browser.new_context(**self.device)
        
        if re.search('Mobile', self.device['user_agent']): profile_path = '/config/profile_mobile'
        elif re.search('Linux', self.device['user_agent']): profile_path = '/config/profile_linux'
        elif re.search('Win64', self.device['user_agent']): profile_path = '/config/profile_win'

        #self.context = playwright.firefox.launch_persistent_context(profile_path,headless=False,firefox_user_prefs=self.firefox_user_prefs,**self.device)
        #self.context = playwright.firefox.launch_persistent_context(profile_path,headless=False,firefox_user_prefs=self.firefox_user_prefs,**self.device)
        self.context = playwright.firefox.launch_persistent_context(profile_path,headless=True,firefox_user_prefs=self.firefox_user_prefs,**self.device)


        # Block unnecessary requests
        self.context.route("**/*", lambda route: self.abort_route(route))
        self.context.set_default_navigation_timeout(self.timeout)
        self.context.clear_cookies()
        self.context.clear_permissions()

        self.page = self.context.new_page()
        self.page = self.context.pages[0]

        # Set Default Timeouts
        self.page.set_default_timeout(self.timeout)
        expect.set_options(timeout=self.timeout)

        # Help reduce bot detection
        self.page.add_init_script(self.webdriver_script)

        if  SUPPORT and \
            os.path.exists('/config/'):
            self.page.on("console", lambda consolemessage: debug_support_logger.debug(f"Console Message: {consolemessage.text}"))
            self.page.on("pageerror", self.check_pageerror)
        self.page.on("close", self.check_close)
        self.page.on("domcontentloaded", self.check_domcontentloaded)
        self.page.on("frameattached", self.check_frameattached)
        self.page.on("framenavigated", self.check_framenavigated)
        self.page.on("load", self.check_load)
        self.page.on("response", self.check_response)
        self.page.on("request", self.check_request)
        self.page.on("requestfailed", self.check_requestfailed)
        self.page.on("requestfinished", self.check_requestfinished)

    def akamai_sleep(self):
        for sleep in range(5):
            done = sleep+1
            togo = 5-sleep
            time.sleep(3600) # Sleep for 1 hr then log progress
            logger.error(f"In Akamai Access Denied sleep cycle")
            logger.error(f"{done} {'hour' if done == 1 else 'hours'} done, {togo} to go")

    def two_step_verification_handler(self):
        logger.error(f"Two-Step Verification is turned on. Exiting...")
        exit(95)

    def abort_route(self, route: Route) :
        # Necessary Xfinity domains
        good_xfinity_domains = ['*.xfinity.com', '*.comcast.net', 'static.cimcontent.net', '*.codebig2.net']
        regex_good_xfinity_domains = ['xfinity.com', 'comcast.net', 'static.cimcontent.net', 'codebig2.net']

        # Domains blocked base on Origin Ad Block filters
        regex_block_xfinity_domains = ['.ico$',
                                       '/akam/',
                                       #re.compile('xfinity.com/(?:\w+\/{1}){4,}\w+'), # Will cause Akamai Access Denied
                                       'login.xfinity.com/static/ui-common/',
                                       'login.xfinity.com/static/images/',
                                       'assets.xfinity.com/assets/dotcom/adrum/', 
                                       'xfinity.com/event/',
                                       'metrics.xfinity.com',
                                       'serviceo.xfinity.com',
                                       'serviceos.xfinity.com',
                                       'target.xfinity.com'
                                       ] + xfinity_block_list
        
        # Block unnecessary resources
        bad_resource_types = ['image', 'images', 'stylesheet', 'media', 'font']

        if  route.request.resource_type not in bad_resource_types and \
            any(fnmatch.fnmatch(urllib.parse.urlsplit(route.request.url).netloc, pattern) for pattern in good_xfinity_domains):
            for urls in regex_block_xfinity_domains:
                if re.search(urls, urllib.parse.urlsplit(route.request.url).hostname + urllib.parse.urlsplit(route.request.url).path):
                    if SUPPORT: debug_support_logger.debug(f"Blocked URL: {route.request.url}")
                    #logger.info(f"Blocked URL: {route.request.url}")
                    route.abort('blockedbyclient')        
                    return None
            for urls in regex_good_xfinity_domains:
                if  re.search(urls, urllib.parse.urlsplit(route.request.url).hostname) and \
                    route.request.resource_type not in bad_resource_types:
                    if SUPPORT: debug_support_logger.debug(f"Good URL: {route.request.url}")
                    #logger.info(f"Good URL: {route.request.url}")
                    route.continue_()     
                    return None
            if SUPPORT: debug_support_logger.debug(f"Good URL: {route.request.url}")
            route.continue_()     
            return None
        else:
            if SUPPORT: debug_support_logger.debug(f"Blocked URL: {route.request.url}")
            route.abort('blockedbyclient')
            return None
        

    def parse_url(self, url: str) -> str:
        split_url = urllib.parse.urlsplit(url, allow_fragments=True)
        if split_url.fragment:
            return split_url.scheme+'://'+split_url.netloc+split_url.path+'#'+split_url.fragment
        else:
            return split_url.scheme+'://'+split_url.netloc+split_url.path


    def camelTo_snake_case(self, string: str) -> str:
        """Converts camelCase strings to snake_case"""
        return ''.join(['_' + i.lower() if i.isupper() else i for i in string]).lstrip('_')


    def debug_support(self) -> None:
        if  SUPPORT and \
            os.path.exists('/config/'):

            datetime_format = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            page_content = self.page.content()
            page_content_hash = hash(base64.b64encode(self.page.content().encode()).decode())
            page_screenshot = self.page.screenshot()
            page_screenshot_hash = hash(base64.b64encode(page_screenshot).decode())
            

            if self.support_page_hash != page_content_hash:
                with open(f"/config/{datetime_format}-page.html", "w") as file:
                    if file.write(page_content):
                        file.close()
                        logger.debug(f"Writing page source to addon_config")
                self.support_page_hash = page_content_hash

            if self.support_page_screenshot_hash != page_screenshot_hash:
                with open(f"/config/{datetime_format}-screenshot.png", "wb") as file:
                    if file.write(page_screenshot):
                        file.close()
                        logger.debug(f"Writing page screenshot to addon_config")
                self.support_page_screenshot_hash = page_screenshot_hash


    def process_usage_json(self, json_data: dict) -> bool:
        _cur_month = json_data['usageMonths'][-1]
        # record current month's information
        # convert key names to 'snake_case'
        attributes = {}
        for k, v in _cur_month.items():
            attributes[self.camelTo_snake_case(k)] = v

        if _cur_month['policy'] == 'limited':
            # extend data for limited accounts
            #attributes['accountNumber'] = json_data['accountNumber']
            attributes['courtesy_used'] = json_data['courtesyUsed']
            attributes['courtesy_remaining'] = json_data['courtesyRemaining']
            attributes['courtesy_allowed'] = json_data['courtesyAllowed']
            attributes['courtesy_months'] = json_data['courtesyMonths']
            attributes['in_paid_overage'] = json_data['inPaidOverage']
            attributes['remaining_usage'] = _cur_month['allowableUsage'] - _cur_month['totalUsage']

        # assign some values as properties
        total_usage = _cur_month['totalUsage']

        json_dict = {}
        json_dict['attributes'] = attributes
        json_dict['attributes']['friendly_name'] = 'Xfinity Usage'
        json_dict['attributes']['unit_of_measurement'] = _cur_month['unitOfMeasure']
        json_dict['attributes']['device_class'] = 'data_size'
        json_dict['attributes']['state_class'] = 'measurement'
        json_dict['attributes']['icon'] = 'mdi:wan'
        json_dict['state'] = total_usage

        if  self.plan_details_data is not None and \
            self.plan_details_data.get('InternetDownloadSpeed') and \
            self.plan_details_data.get('InternetUploadSpeed'):
                json_dict['attributes']['internet_download_speeds_Mbps'] = self.plan_details_data['InternetDownloadSpeed']
                json_dict['attributes']['internet_upload_speeds_Mbps'] = self.plan_details_data['InternetUploadSpeed']

        if is_mqtt_available():
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
            mqtt_client.mqtt_device_config_dict['device']['identifiers'] = mqtt_client.mqtt_device_details_dict.get('mac', [json_dict['attributes']['devices'][0]['id']])
            mqtt_client.mqtt_device_config_dict['device']['model'] = mqtt_client.mqtt_device_details_dict.get('model', json_dict['attributes']['devices'][0]['policyName'])
            mqtt_client.mqtt_device_config_dict['device']['manufacturer'] = mqtt_client.mqtt_device_details_dict.get('make', None)
            mqtt_client.mqtt_device_config_dict['device']['name'] = "Xfinity"
            """
            if bool(mqtt_client.mqtt_device_details_dict):
                mqtt_client.mqtt_device_config_dict['device']['identifiers'] = mqtt_client.mqtt_device_details_dict.get('mac',[json_dict['attributes']['devices'][0]['id']])
                mqtt_client.mqtt_device_config_dict['device']['model'] = mqtt_client.mqtt_device_details_dict.get('model',json_dict['attributes']['devices'][0]['policyName'])
                mqtt_client.mqtt_device_config_dict['device']['manufacturer'] = mqtt_client.mqtt_device_details_dict.get('make', None)
                #mqtt_client.mqtt_device_config_dict['device']['serial_number'] = mqtt_client.mqtt_device_details_dict['serialNumber']
                #mqtt_client.mqtt_device_config_dict['device']['name'] = f"{mqtt_client.mqtt_device_details_dict['make']} {mqtt_client.mqtt_device_details_dict['model']}"
                mqtt_client.mqtt_device_config_dict['device']['name'] = "Xfinity"
            else:    
                mqtt_client.mqtt_device_config_dict['device']['identifiers'] = [json_dict['attributes']['devices'][0]['id']]
                mqtt_client.mqtt_device_config_dict['device']['model'] = json_dict['attributes']['devices'][0]['policyName']
                mqtt_client.mqtt_device_config_dict['device']['name'] = f"Xfinity"
            """
            
            # MQTT Home Assistant Sensor State
            mqtt_client.mqtt_state = json_dict['state']
            # MQTT Home Assistant Sensor Attributes
            mqtt_client.mqtt_json_attributes_dict = json_dict['attributes']

        if total_usage >= 0:
            self.usage_data = json.dumps(json_dict)
            logger.info(f"Usage data retrieved and processed")
            logger.debug(f"Usage Data JSON: {self.usage_data}")
        else:
            self.usage_data = None


    def update_sensor_file(self) -> None:
        if  self.usage_data is not None and \
            os.path.exists('/config/'):

            with open(SENSOR_BACKUP, 'w') as file:
                if file.write(self.usage_data):
                    logger.info(f"Updating Sensor File")
                    file.close()


    def update_ha_sensor(self) -> None:
        if  bool(self.BASHIO_SUPERVISOR_API) and \
            bool(self.BASHIO_SUPERVISOR_TOKEN) and \
            self.usage_data is not None:

            headers = {
                'Authorization': 'Bearer ' + self.BASHIO_SUPERVISOR_TOKEN,
                'Content-Type': 'application/json',
            }

            logger.info(f"Updating Sensor: {self.SENSOR_NAME}")

            response = requests.post(
                self.SENSOR_URL,
                headers=headers,
                data=self.usage_data
            )

            if response.ok:
                return None

            if response.status_code == 401:
                logger.error(f"Unable to authenticate with the API, permission denied")
            else:
                logger.error(f"Response Status Code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                logger.debug(f"Response Raw: {response.raw}")

        return None


    def check_jwt_session(self,response: Response) -> None:
        session_data = jwt.decode(response.header_value('x-ssm-token'), options={"verify_signature": False})

        if  session_data['sessionType'] == 'FULL' and \
            session_data['exp'] > time.time() and \
            self.is_session_active == False:
            self.is_session_active = True
            logger.info(f"Updating Session Details")
            logger.debug(f"Updating Session Details {response.url}")
            logger.debug(f"Updating Session Details is_session_active: {self.is_session_active}")
            logger.debug(f"Updating Session Details session time left: {session_data['exp'] - int(time.time())} seconds")
            logger.debug(f"Updating Session Details {json.dumps(session_data)}")

        elif session_data['sessionType'] != 'FULL' or \
            session_data['exp'] <= time.time():
            self.is_session_active = False

    def check_pageerror(self, exc) -> None:
        debug_support_logger.debug(f"Page Error: uncaught exception: {exc}")
    
    def check_frameattached(self, frame: Frame) -> None:
        logger.debug(f"Page frameattached: {frame.page.url}") 

    def check_close(self, page: Page) -> None:
        logger.debug(f"Page close: {page.url}")

    def check_domcontentloaded(self, page: Page) -> None:
        logger.debug(f"Page domcontentloaded: {page.url}")

    def check_load(self, page: Page) -> None:
        logger.debug(f"Page load: {page.url}")

    def check_framenavigated(self, frame: Frame) -> None:
        logger.debug(f"Page framenavigated: {frame.page.url}")

    def check_request(self, request: Request) -> None:
        self.pending_requests.append(request)

    def check_requestfailed(self, request: Request) -> None:
        self.pending_requests.remove(request)

    def check_requestfinished(self, request: Request) -> None:
        self.pending_requests.remove(request)

    def check_response(self,response: Response) -> None:
        logger.debug(f"Network Response: {response.status} {response.url}")

        if response.ok:
            if 'x-ssm-token' in response.headers:
                self.check_jwt_session(response)

            if response.url == self.Plan_Details_JSON_Url:
                self.plan_details_data = {}
                test = response.json()["shoppingOfferDetail"]["dynamicParameters"]
                download_speed = response.json()["shoppingOfferDetail"]["dynamicParameters"][1]["value"].split(" ", 1)[0]
                upload_speed = response.json()["shoppingOfferDetail"]["dynamicParameters"][0]["value"].split(" ",1)[0]
                self.plan_details_data['InternetDownloadSpeed'] = int(download_speed)
                self.plan_details_data['InternetUploadSpeed'] = int(upload_speed)
                logger.info(f"Updating Plan Details")
                logger.debug(f"Updating Plan Details {json.dumps(self.plan_details_data)}")
            """
                {   "accountNumber": "9999999999999999",
                    "courtesyUsed": 0,
                    "courtesyRemaining": 1,
                    "courtesyAllowed": 1,
                    "courtesyMonths": [
                        "03/2023"
                    ],
                    "inPaidOverage": false,
                    "displayUsage": true,
                    "usageMonths": [
                    {   # Array -1 Current month is last element in array
                        "policyName": "1.2 Terabyte Data Plan",
                        "startDate": "04/01/2024",
                        "endDate": "04/30/2024",
                        "homeUsage": 585,
                        "wifiUsage": 0,
                        "totalUsage": 585,
                        "allowableUsage": 1229,
                        "unitOfMeasure": "GB",
                        "displayUsage": true,
                        "devices": [{
                            "id": "AA:BB:1A:B2:C3:4D",
                            "usage": 592,
                            "policyName": "XI Superfast"
                        }],
                        "additionalBlocksUsed": 0,
                        "additionalCostPerBlock": 10,
                        "additionalUnitsPerBlock": 50,
                        "additionalBlockSize": 50,
                        "additionalIncluded": 0,
                        "additionalUsed": 0,
                        "additionalPercentUsed": 0,
                        "additionalRemaining": 0,
                        "billableOverage": 0,
                        "overageCharges": 0,
                        "overageUsed": 0,
                        "currentCreditAmount": 0,
                        "maxCreditAmount": 0,
                        "maximumOverageCharge": 100,
                        "policy": "limited"
                        }]}
            """
            if response.url == self.Usage_JSON_Url:
                if response.json() is not None: self.usage_details_data = response.json()
                logger.info(f"Updating Usage Details")
                logger.debug(f"Updating Usage Details {textwrap.shorten(json.dumps(response.json()), width=120, placeholder='...')}")

            """
            {
                "services": {
                    "internet": {
                        "devices": [
                            {
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
                            }
                        ]
                    }
                }
            }
            """
            if response.url == self.Device_Details_JSON_Url:
                if response.json() is not None: self.device_details_data = response.json()['services']['internet']['devices'][0]['deviceDetails']
                logger.info(f"Updating Device Details")
                logger.debug(f"Updating Device Details {json.dumps(response.json())}")                


    def get_device_details_data(self) -> None:
        self.page.goto(self.Device_Details_Url)
        logger.info(f"Loading Device Data (URL: {self.parse_url(self.page.url)})")
        
        # Wait for ShimmerLoader to attach and then unattach
        expect(self.page.locator("div#app")).to_be_attached()
        try:
            expect(self.page.locator('div#app p[class^="connection-"]').first).to_contain_text(re.compile(r".+"))
        except:
            div_app_p_count = self.page.locator('div#app p[class^="connection-"]').count()
            if div_app_p_count > 0:
                logger.error(f"div#app p Count: {div_app_p_count}")
                for div_app_p in self.page.locator('div#app p[class^="connection-"]').all():
                    logger.error(f"div#app p inner html: {div_app_p.inner_html()}")    


    def run(self) -> None:
        """
        Main business loop.
            * Go to Usage URL
            * Login if needed
            * Process usage data for HA Sensor
            * Push usage to HA Sensor

        Returns: None
        """
        self.usage_data = None
        self.plan_details_data = None
        self.usage_details_data = None
        self.is_session_active = False

        # Username Section
        self.page_response = self.page.goto(self.Internet_Service_Url)
        logger.info(f"Loading Internet Usage (URL: {self.parse_url(self.page.url)})")
        try:
            self.page.wait_for_url(f'{self.Login_Url}*')
            expect(self.page).to_have_title('Sign in to Xfinity')
            expect(self.page.locator("input#user")).to_be_attached()
            expect(self.page.locator("input#user")).to_be_editable()
        except:
            return None
        
        logger.info(f"Entering username (URL: {self.parse_url(self.page.url)})")
        if self.slow_down_login: time.sleep(random.uniform(.3, .6))

        all_inputs = self.page.get_by_role("textbox").all()
        if len(all_inputs) != 1:
            raise AssertionError("Username page: not the right amount of inputs")

        #self.session_storage = self.page.evaluate("() => JSON.stringify(sessionStorage)")

        for input in all_inputs:
            logger.debug(f"{input.evaluate('el => el.outerHTML')}")

        self.page.locator("input#user").click()
        if self.slow_down_login: time.sleep(random.uniform(.3, .6))
        self.page.locator("input#user").press_sequentially(self.xfinity_username, delay=150)
        if self.slow_down_login: time.sleep(random.uniform(.3, .6))
        self.debug_support()
        self.page.locator("input#user").press("Enter")
        #self.page.locator("button[type=submit]#sign_in").click()
        self.debug_support()

        # Password Section
        try:
            self.page.wait_for_url(f'{self.Login_Url}*')
            expect(self.page).to_have_title('Sign in to Xfinity')
            expect(self.page.locator("input#passwd")).to_be_attached()
            expect(self.page.locator("input#passwd")).to_be_editable()
        except:
            if self.page.title() == 'Access Denied':
                if run_playwright.statistics['attempt_number'] > 3:
                    logger.error(f"{ordinal(run_playwright.statistics['attempt_number'])} Akamai Access Denied error!!")
                    logger.error(f"Lets sleep for 6 hours and then try again")
                    self.akamai_sleep()
                else:
                    raise AssertionError(f"{ordinal(run_playwright.statistics['attempt_number'])} Akamai Access Denied error!!")
            else:
                for input in self.page.get_by_role("textbox").all():
                    logger.debug(f"{input.evaluate('el => el.outerHTML')}")


        logger.info(f"Entering password (URL: {self.parse_url(self.page.url)})")
        if self.slow_down_login: time.sleep(random.uniform(.3, .6))

        all_inputs = self.page.get_by_role("textbox").all()
        if len(all_inputs) != 2:
                raise AssertionError("not the right amount of inputs")

        if self.page.locator("input#user").get_attribute("value") != self.xfinity_username:
            for input in all_inputs:
                logger.debug(f"{input.evaluate('el => el.outerHTML')}")
            raise AssertionError("Password form page is missing the user id")

        self.page.locator("input#passwd").click()
        if self.slow_down_login: time.sleep(random.uniform(.3, .6))
        self.page.locator("input#passwd").press_sequentially(self.xfinity_password, delay=175)
        if self.slow_down_login: time.sleep(random.uniform(.3, .6))
        self.debug_support()
        self.form_signin = self.page.locator("form[name=\"signin\"]").inner_html()
        for input in self.page.get_by_role("textbox").all():
            logger.debug(f"{input.evaluate('el => el.outerHTML')}")
                         
        self.page.locator("input#passwd").press("Enter")
        #self.page.locator("button[type=submit]#sign_in").click()
        self.debug_support()

        # Check for Two Step Verification
        try:
            self.page.wait_for_url(re.compile('https://www\.xfinity\.com(?:/learn/internet-service){0,1}/auth'))
            expect(self.page).not_to_have_title('Sign in to Xfinity')
        except:
            logger.info(f"Two Step Verification Check: Page Title {self.page.title()}")
            logger.info(f"Two Step Verification Check: Page Url {self.page.url}")
            for input in self.page.get_by_role("textbox").all():
                logger.debug(f"{input.evaluate('el => el.outerHTML')}")
                if re.search('id="user"',input.evaluate('el => el.outerHTML')):
                    raise AssertionError("Password form submission failed")

                if  re.search('id="verificationCode"',input.evaluate('el => el.outerHTML')) and \
                    self.page.locator("input#verificationCode").is_enabled():
                        self.two_step_verification_handler()
            
        
        # Loading Xfinity Internet Customer Overview Page
        try:
            #logger.info(f"try: {self.page.url}")
            expect(self.page).to_have_url(self.Internet_Service_Url)
        except:
            # if not Internet_Service_Url then we landed at www.xfinity.com/auth
            # session may be active just ended up in the wrong place
            # Try to load Internet Service page
            self.page.goto(self.Internet_Service_Url)
            logger.info(f"Reloading Internet Usage (URL: {self.parse_url(self.page.url)})")


        logger.debug(f"Loading page (URL: {self.page.url})")

        # Wait for ShimmerLoader to be attached and then unattached
        expect(self.page.get_by_test_id('ShimmerLoader')).to_be_attached()
        self.debug_support()
        expect(self.page.get_by_test_id('ShimmerLoader')).not_to_be_attached()
        self.debug_support()
    
        # Wait for plan usage table to load with data
        try:
            self.debug_support()
            expect(self.page.get_by_test_id('planRowDetail').nth(2).filter(has=self.page.locator(f"prism-button[href^=\"https://\"]"))).to_be_visible()
            self.debug_support()
        except:
            logger.error(f"planRowDetail Count: {self.page.get_by_test_id('planRowDetail').count()}")
            logger.error(f"planRowDetail Row 3 inner html: {self.page.get_by_test_id('planRowDetail').nth(2).inner_html()}")
            logger.error(f"planRowDetail Row 3 text content: {self.page.get_by_test_id('planRowDetail').nth(2).text_content()}")

        logger.debug(f"Finished loading page (URL: {self.page.url})")
        
        # If we have the plan and usage data, success and lets process it
        if self.plan_details_data is not None and self.usage_details_data is not None:

            # If MQTT is enable attempt to gather real cable modem details
            if is_mqtt_available() and bool(mqtt_client.mqtt_device_details_dict) is False:
                self.get_device_details_data()
                mqtt_client.mqtt_device_details_dict = self.device_details_data

            # Now compile the usage data for the sensor
            self.process_usage_json(self.usage_details_data)

            #if  self.is_session_active and self.usage_data is not None:
            if self.usage_data is not None and is_mqtt_available() is False:
                logger.debug(f"Sensor API Url: {self.SENSOR_URL}")
                self.update_ha_sensor()
                self.update_sensor_file()

        # Plan and usage data is missing throw an Assertion to cause retry
        else:
            self.debug_support()
            raise AssertionError("Usage page did not load correctly, missing usage data")

# Retry
# Stop retrying after 15 attempts
# Wait exponentially
#
@retry(stop=stop_after_attempt(15),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True)
def run_playwright() -> None:
    """
        * Start Playwright
        * Initialize XfinityUsage class
        * usage.run() to get usage data and push usage to HA Sensor
        * Stop Playwright

    Returns: None
    """

    if run_playwright.statistics['attempt_number'] > 1:
        logger.warning(f"{ordinal(run_playwright.statistics['attempt_number'] - 1)} retry")

    with sync_playwright() as playwright:
        usage = XfinityUsage(playwright)
        usage.run()

        if is_mqtt_available() and mqtt_client.is_connected_mqtt():
            mqtt_client.publish_mqtt(usage.usage_data)

        usage.context.close()
        #usage.browser.close()
        playwright.stop()



if __name__ == '__main__':
    if is_mqtt_available():
        mqtt_client = XfinityMqtt()

    """
        * run_playwright does all the work
        * sleep for POLLING_RATE

    Returns: None
    """
    logger.info(f"Xfinity Internet Usage Starting")
    while True:
        try:
            run_playwright()
            
            if SUPPORT: exit(99)

            logger.info(f"Sleeping for {int(POLLING_RATE)} seconds")
            sleep(POLLING_RATE)
        except:
            mqtt_client.disconnect_mqtt()
            exit(98)



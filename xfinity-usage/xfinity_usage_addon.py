import asyncio
import base64
import fnmatch
import glob
import json
import jwt
import logging
import os
import random
import re
import requests
import shutil
import socket
import ssl
import sys
import textwrap
import time
import urllib.parse
# from bs4 import BeautifulSoup
from datetime import datetime
from enum import Enum
from tenacity import stop_after_attempt,  wait_exponential, retry, before_sleep_log
from time import sleep
from paho.mqtt import client as mqtt
from pathlib import Path
from playwright.async_api import async_playwright, Playwright, Route, Response, Request, Frame, Page, expect

# Browser mode
HEADLESS=json.loads(os.environ.get('HEADLESS', 'true').lower()) # Convert HEADLESS string into boolean

# Login slow variables
SLOW_DOWN_MIN = os.environ.get('SLOW_DOWN_MIN', 0.5)
SLOW_DOWN_MAX = os.environ.get('SLOW_DOWN_MAX', 1.2)
SLOW_DOWN_LOGIN = True

#Randomize User Agent variables
ANDROID_MIN_VERSION = os.environ.get('ANDROID_MIN_VERSION', 10)
ANDROID_MAX_VERSION = os.environ.get('ANDROID_MAX_VERSION', 10)
FIREFOX_MIN_VERSION = os.environ.get('FIREFOX_MIN_VERSION', 120)
FIREFOX_MAX_VERSION = os.environ.get('FIREFOX_MAX_VERSION', 124)

# GLOBAL URLS
VIEW_USAGE_URL = 'https://customer.xfinity.com/#/devices#usage'
VIEW_WIFI_URL = 'https://customer.xfinity.com/settings/wifi'
INTERNET_SERVICE_URL = 'https://www.xfinity.com/learn/internet-service/auth'
AUTH_URL = 'https://content.xfinity.com/securelogin/cima?sc_site=xfinity-learn-ui&continue=https://www.xfinity.com/auth'
#AUTH_URL = 'https://content.xfinity.com/securelogin/cima?sc_site=xfinity-learn-ui&continue=https://www.xfinity.com/learn/internet-service/auth'
LOGIN_URL = 'https://login.xfinity.com/login'
LOGOUT_URL = 'https://www.xfinity.com/overview'
USAGE_JSON_URL = 'https://api.sc.xfinity.com/session/csp/selfhelp/account/me/services/internet/usage'
PLAN_DETAILS_JSON_URL = 'https://api.sc.xfinity.com/session/plan'
DEVICE_DETAILS_URL = 'https://www.xfinity.com/support/status'
DEVICE_DETAILS_JSON_URL = 'https://api.sc.xfinity.com/devices/status'
SESSION_URL = 'https://api.sc.xfinity.com/session'

# Xfinity authentication
XFINITY_USERNAME = os.environ.get('XFINITY_USERNAME', None)
XFINITY_PASSWORD = os.environ.get('XFINITY_PASSWORD', None)

# Playwright timeout
PAGE_TIMEOUT = int(os.environ.get('PAGE_TIMEOUT', 60))

# MQTT
MQTT_SERVICE = json.loads(os.environ.get('MQTT_SERVICE', 'false').lower()) # Convert MQTT_SERVICE string into boolean
MQTT_HOST = os.environ.get('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', None)
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', None)
MQTT_RAW_USAGE = json.loads(os.environ.get('MQTT_RAW_USAGE', 'false').lower()) # Convert MQTT_RAW_USAGE string into boolean
MQTT_CLIENT = None

BASHIO_SUPERVISOR_API = os.environ.get('BASHIO_SUPERVISOR_API', '')
BASHIO_SUPERVISOR_TOKEN = os.environ.get('BASHIO_SUPERVISOR_TOKEN', '')
SENSOR_NAME = "sensor.xfinity_usage"
SENSOR_URL = f"{BASHIO_SUPERVISOR_API}/core/api/states/{SENSOR_NAME}"
SENSOR_BACKUP = '/config/.sensor-backup'

# Logging 
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
DEBUG_LOGGER_FILE = '/config/xfinity.log'
DEBUG_SUPPORT = json.loads(os.environ.get('DEBUG_SUPPORT', 'false').lower()) # Convert DEBUG_SUPPORT string into boolean
if DEBUG_SUPPORT: LOG_LEVEL = 'DEBUG'

# Possible browser profiles
profile_paths = [
                '/config/profile_mobile',
                '/config/profile_linux',
                '/config/profile_linux_ubuntu',
                '/config/profile_linux_fedora',
                '/config/profile_win'
                ]

# Remove browser profile path upon startup
for profile_path in profile_paths:
    if Path(profile_path).exists() and Path(profile_path).is_dir(): shutil.rmtree(profile_path)

# Remove debug log file upon script startup
if os.path.exists(DEBUG_LOGGER_FILE): os.remove(DEBUG_LOGGER_FILE)

#if len(os.environ.get('LOG_LEVEL', 'INFO').upper().split('_')) > 1 and 'DEBUG_SUPPORT' == os.environ.get('LOG_LEVEL', 'INFO').upper().split('_')[1] : DEBUG_SUPPORT = True

logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')

if LOG_LEVEL == 'DEBUG':
    file_handler = logging.FileHandler(DEBUG_LOGGER_FILE,mode='w')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler) 
    
    if DEBUG_SUPPORT:
        debug_support_logger = logging.getLogger(__name__ + '.file_logger')
        debug_support_logger.addHandler(file_handler)
        debug_support_logger.propagate = False

    for name, value in sorted(os.environ.items()):
        if name == 'XFINITY_PASSWORD':
            value = base64.b64encode(base64.b64encode(value.encode()).decode().strip('=').encode()).decode().strip('=')
        logger.debug(f"{name}: {value}")

def get_current_unix_epoch() -> float:
    return time.time()

def ordinal(n) -> str:
    s = ('th', 'st', 'nd', 'rd') + ('th',)*10
    v = n%100
    if v > 13:
      return f'{n}{s[v%10]}'
    else:
      return f'{n}{s[v]}'

def is_mqtt_available() -> bool:
    if MQTT_SERVICE and bool(MQTT_HOST) and bool(MQTT_PORT):
        return True
    else:
        return False

def parse_url(url: str) -> str:
    split_url = urllib.parse.urlsplit(url, allow_fragments=True)
    if split_url.fragment:
        return split_url.scheme+'://'+split_url.netloc+split_url.path+'#'+split_url.fragment
    else:
        return split_url.scheme+'://'+split_url.netloc+split_url.path

async def akamai_sleep():
    for sleep in range(5):
        done = sleep+1
        togo = 5-sleep
        await asyncio.sleep(3600) # Sleep for 1 hr then log progress
        logger.error(f"In Akamai Access Denied sleep cycle")
        logger.error(f"{done} {'hour' if done == 1 else 'hours'} done, {togo} to go")

def two_step_verification_handler() -> None:
    logger.error(f"Two-Step Verification is turned on. Exiting...")
    exit(exit_code.TWO_STEP_VERIFICATION.value)

async def get_slow_down_login():
    if SLOW_DOWN_LOGIN:
        await asyncio.sleep(random.uniform(SLOW_DOWN_MIN, SLOW_DOWN_MAX))
        

class exit_code(Enum):
    SUCCESS = 0
    MISSING_LOGIN_CONFIG = 80
    MISSING_MQTT_CONFIG = 81
    TOO_MANY_USERNAME = 94
    TOO_MANY_PASSWORD = 95
    BAD_PASSWORD = 96
    TWO_STEP_VERIFICATION = 97
    MAIN_EXCEPTION = 98
    DEBUG_SUPPORT = 99

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
    def __init__(self, playwright: Playwright):
        #super().__init__()
        self.timeout = PAGE_TIMEOUT * 1000
        self.playwright = playwright
        self.form_stage = []
        self.username_count = 0
        self.password_count = 0

        self.is_session_active = False
        self.session_details = {}
        self.usage_data = None
        self.usage_details_data = None
        self.plan_details_data = None
        self.device_details_data = {}

        self.reload_counter = 0
        self.pending_requests = []
        self.FIREFOX_VERSION = str(random.randint(FIREFOX_MIN_VERSION, FIREFOX_MAX_VERSION))
        self.ANDROID_VERSION = str(random.randint(ANDROID_MIN_VERSION, ANDROID_MAX_VERSION))
        self.page_title = ''
        #self.frameattached_url = ''
        #self.framenavigated_url = ''

        if DEBUG_SUPPORT: self.support_page_hash = int; self.support_page_screenshot_hash = int


    async def start(self):
        if is_mqtt_available() is False and os.path.isfile(SENSOR_BACKUP) and os.path.getsize(SENSOR_BACKUP):
            with open(SENSOR_BACKUP, 'r') as file:
                self.usage_data = file.read()
                await self.update_ha_sensor()

        self.device = await self.get_browser_device()
        #self.profile_path = await self.get_browser_profile_path()
        self.profile_path = '/config/profile'

        #logger.info(f"Launching {textwrap.shorten(self.device['user_agent'], width=77, placeholder='...')}")
        
        self.firefox_user_prefs={'webgl.disabled': True, 'network.http.http2.enabled': False}
        #self.firefox_user_prefs={'webgl.disabled': True}
        #self.firefox_user_prefs={'webgl.disabled': False}
        self.webdriver_script = "delete Object.getPrototypeOf(navigator).webdriver"
        #self.webdriver_script = ""

        #self.browser = playwright.firefox.launch(headless=False,slow_mo=1000,firefox_user_prefs=self.firefox_user_prefs)
        #self.browser = await self.playwright.firefox.launch(headless=HEADLESS,firefox_user_prefs=self.firefox_user_prefs)
        #self.browser = playwright.firefox.launch(headless=False,firefox_user_prefs=self.firefox_user_prefs,proxy={"server": "http://127.0.0.1:3128"})
        #self.browser = playwright.firefox.launch(headless=True,firefox_user_prefs=self.firefox_user_prefs)
        
        #self.browser = playwright.chromium.launch(headless=False,channel='chrome')
        #if self.browser.browser_type.name == 'firefox': self.context = await self.browser.new_context(**self.device)
        #else: self.context = await self.browser.new_context(**self.device,is_mobile=True)
        

        #self.context = playwright.firefox.launch_persistent_context(profile_path,headless=False,firefox_user_prefs=self.firefox_user_prefs,**self.device)
        #self.context = playwright.firefox.launch_persistent_context(profile_path,headless=False,firefox_user_prefs=self.firefox_user_prefs,**self.device)
        self.context = await self.playwright.firefox.launch_persistent_context(self.profile_path,headless=HEADLESS,firefox_user_prefs=self.firefox_user_prefs,**self.device)


        # Block unnecessary requests
        await self.context.route("**/*", lambda route: self.abort_route(route))
        self.context.set_default_navigation_timeout(self.timeout)
        #await self.context.clear_cookies()
        #await self.context.clear_permissions()
        self.context.on("response", self.check_response)
        self.context.on("request", self.check_request)
        self.context.on("requestfailed", self.check_requestfailed)
        self.context.on("requestfinished", self.check_requestfinished)


        #self.page = await self.context.new_page()
        self.page = await self.get_new_page()

        logger.info(f"Launching {textwrap.shorten(await self.page.evaluate('navigator.userAgent'), width=77, placeholder='...')}")

        if  DEBUG_SUPPORT and \
            os.path.exists('/config/'):
            self.page.on("console", lambda consolemessage: debug_support_logger.debug(f"Console Message: {consolemessage.text}"))
            self.page.on("pageerror", self.check_pageerror)
        self.page.on("close", self.check_close)
        self.page.on("domcontentloaded", self.check_domcontentloaded)
        self.page.on("frameattached", self.check_frameattached)
        self.page.on("framenavigated", self.check_framenavigated)
        self.page.on("load", self.check_load)

    async def done(self) -> None:
        await self.goto_logout()
        if len(self.pending_requests) > 0:
            await self.page.wait_for_load_state('networkidle')
        for page in self.context.pages:
            await page.close()
        await self.context.close()
        await self.playwright.stop()


    async def get_new_page(self) -> Page:
        _page = await self.context.new_page()

        # Set Default Timeouts
        _page.set_default_timeout(self.timeout)
        expect.set_options(timeout=self.timeout)

        # Help reduce bot detection
        await _page.add_init_script(self.webdriver_script)

        return _page

    async def get_browser_device(self) -> dict:
        # Help reduce bot detection
        device_choices = []
        device_choices.append({
            "user_agent": "Mozilla/5.0 (Android "+self.ANDROID_VERSION+"; Mobile; rv:"+self.FIREFOX_VERSION+".0) Gecko/"+self.FIREFOX_VERSION+".0 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 414,"height": 896}, "viewport": {"width": 414,"height": 896},
            "device_scale_factor": 2, "has_touch": True
        })
        """
        device_choices.append({
            "user_agent": "Mozilla/5.0 (Android "+self.ANDROID_VERSION+"; Mobile; rv:"+self.FIREFOX_VERSION+".0) Gecko/"+self.FIREFOX_VERSION+".0 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 414,"height": 896}, "viewport": {"width": 414,"height": 896},
            "device_scale_factor": 2, "has_touch": True
        })
        device_choices.append({
            "user_agent": "Mozilla/5.0 (Android 12; Mobile; rv:"+self.FIREFOX_VERSION+".0) Gecko/"+self.FIREFOX_VERSION+".0 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 414,"height": 896}, "viewport": {"width": 414,"height": 896},
            "device_scale_factor": 2, "has_touch": True
        })
        device_choices.append({
            "user_agent": "Mozilla/5.0 (Android 11; Mobile; rv:"+self.FIREFOX_VERSION+".0) Gecko/"+self.FIREFOX_VERSION+".0 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 414,"height": 896}, "viewport": {"width": 414,"height": 896},
            "device_scale_factor": 2, "has_touch": True
        })
        device_choices.append({
            "user_agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:"+self.FIREFOX_VERSION+".0) Gecko/20100101 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 1920,"height": 1080}, "viewport": {"width": 1920,"height": 1080},
            "device_scale_factor": 1, "is_mobile": False, "has_touch": False
        })
        device_choices.append({
            "user_agent": "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:"+self.FIREFOX_VERSION+".0) Gecko/20100101 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 1920,"height": 1080}, "viewport": {"width": 1920,"height": 1080},
            "device_scale_factor": 1, "is_mobile": False, "has_touch": False
        })
        device_choices.append({
            "user_agent": "Mozilla/5.0 (X11; Linux; Linux x86_64; rv:"+self.FIREFOX_VERSION+".0) Gecko/20100101 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 1920,"height": 1080}, "viewport": {"width": 1920,"height": 1080},
            "device_scale_factor": 1, "is_mobile": False, "has_touch": False
        })
        device_choices.append({
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:"+self.FIREFOX_VERSION+".0) Gecko/20100101 Firefox/"+self.FIREFOX_VERSION+".0",
            "screen": {"width": 1366,"height": 768}, "viewport": {"width": 1366,"height": 768},
            "device_scale_factor": 1, "is_mobile": False, "has_touch": False
        })
        """
        return random.choice(device_choices)

    async def get_browser_profile_path(self) -> str:
        if self.device['user_agent']:
            if re.search('Mobile', self.device['user_agent']): return '/config/profile_mobile'
            elif re.search('Ubuntu', self.device['user_agent']): return '/config/profile_linux_ubuntu'
            elif re.search('Fedora', self.device['user_agent']): return '/config/profile_linux_fedora'
            elif re.search('Linux', self.device['user_agent']): return '/config/profile_linux'
            elif re.search('Win64', self.device['user_agent']): return '/config/profile_win'    
        return '/config/profile'

    async def abort_route(self, route: Route) :
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
                                       'target.xfinity.com',
                                       'yhm.comcast.net'
                                       ] + xfinity_block_list
        
        # Block unnecessary resources
        bad_resource_types = ['image', 'images', 'stylesheet', 'media', 'font']

        if  route.request.resource_type not in bad_resource_types and \
            any(fnmatch.fnmatch(urllib.parse.urlsplit(route.request.url).netloc, pattern) for pattern in good_xfinity_domains):
            for urls in regex_block_xfinity_domains:
                if re.search(urls, urllib.parse.urlsplit(route.request.url).hostname + urllib.parse.urlsplit(route.request.url).path):
                    if DEBUG_SUPPORT: debug_support_logger.debug(f"Blocked URL: {route.request.url}")
                    #logger.info(f"Blocked URL: {route.request.url}")
                    await route.abort('blockedbyclient')        
                    return None
            for urls in regex_good_xfinity_domains:
                if  re.search(urls, urllib.parse.urlsplit(route.request.url).hostname) and \
                    route.request.resource_type not in bad_resource_types:
                    if DEBUG_SUPPORT: debug_support_logger.debug(f"Good URL: {route.request.url}")
                    #logger.info(f"Good URL: {route.request.url}")
                    await route.continue_()     
                    return None
            if DEBUG_SUPPORT: debug_support_logger.debug(f"Good URL: {route.request.url}")
            await route.continue_()     
            return None
        else:
            if DEBUG_SUPPORT: debug_support_logger.debug(f"Blocked URL: {route.request.url}")
            await route.abort('blockedbyclient')
            return None
        

    def camelTo_snake_case(self, string: str) -> str:
        """Converts camelCase strings to snake_case"""
        return ''.join(['_' + i.lower() if i.isupper() else i for i in string]).lstrip('_')


    async def debug_support(self) -> None:
        if  DEBUG_SUPPORT and \
            os.path.exists('/config/'):

            datetime_format = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            page_content = await self.page.content()
            page_content_hash = hash(base64.b64encode(await self.page.content().encode()).decode())
            page_screenshot = await self.page.screenshot()
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


    async def process_usage_json(self, _raw_usage: dict) -> bool:
        _cur_month = _raw_usage['usageMonths'][-1]
        # record current month's information
        # convert key names to 'snake_case'
        attributes = {}
        for k, v in _cur_month.items():
            attributes[self.camelTo_snake_case(k)] = v

        if _cur_month['policy'] == 'limited':
            # extend data for limited accounts
            #attributes['accountNumber'] = _raw_usage['accountNumber']
            attributes['courtesy_used'] = _raw_usage['courtesyUsed']
            attributes['courtesy_remaining'] = _raw_usage['courtesyRemaining']
            attributes['courtesy_allowed'] = _raw_usage['courtesyAllowed']
            attributes['courtesy_months'] = _raw_usage['courtesyMonths']
            attributes['in_paid_overage'] = _raw_usage['inPaidOverage']
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
            mqtt_client.mqtt_device_config_dict['device']['manufacturer'] = mqtt_client.mqtt_device_details_dict.get('make', None) or 'unknown'
            mqtt_client.mqtt_device_config_dict['device']['name'] = "Xfinity"
            
            # MQTT Home Assistant Sensor State
            mqtt_client.mqtt_state = json_dict['state']

            # MQTT Home Assistant Sensor Attributes
            mqtt_client.mqtt_json_attributes_dict = json_dict['attributes']

            # If RAW_USAGE enabled, set MQTT xfinity attributes
            if MQTT_RAW_USAGE:
                mqtt_client.mqtt_json_raw_usage = _raw_usage

        if total_usage >= 0:
            self.usage_data = json.dumps(json_dict)
            logger.info(f"Usage data retrieved and processed")
            logger.debug(f"Usage Data JSON: {self.usage_data}")
        else:
            self.usage_data = None


    async def update_sensor_file(self) -> None:
        if  self.usage_data is not None and \
            os.path.exists('/config/'):

            with open(SENSOR_BACKUP, 'w') as file:
                if file.write(self.usage_data):
                    logger.info(f"Updating Sensor File")
                    file.close()


    async def update_ha_sensor(self) -> None:
        if  bool(BASHIO_SUPERVISOR_API) and \
            bool(BASHIO_SUPERVISOR_TOKEN) and \
            self.usage_data is not None:

            headers = {
                'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
                'Content-Type': 'application/json',
            }

            logger.info(f"Updating Sensor: {SENSOR_NAME}")

            response = requests.post(
                SENSOR_URL,
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


    async def check_jwt_session(self,response: Response) -> None:
        session_data = jwt.decode(await response.header_value('x-ssm-token'), options={"verify_signature": False})

        if  session_data['sessionType'] == 'FULL' and \
            session_data['exp'] > time.time(): # and \
            #self.is_session_active == False:
            self.is_session_active = True
            logger.info(f"Updating Session Details")
            logger.debug(f"Updating Session Details {response.url}")
            logger.debug(f"Updating Session Details is_session_active: {self.is_session_active}")
            logger.debug(f"Updating Session Details session time left: {session_data['exp'] - int(time.time())} seconds")
            logger.debug(f"Updating Session Details {json.dumps(session_data)}")

        elif session_data['sessionType'] != 'FULL' or \
            session_data['exp'] <= time.time():
            self.is_session_active = False


    async def check_pageerror(self, exc) -> None:
        debug_support_logger.debug(f"Page Error: uncaught exception: {exc}")
    
    async def check_frameattached(self, frame: Frame) -> None:
        #self.frameattached_url = frame.page.url
        logger.debug(f"Page frameattached: {frame.page.url}") 

    async def check_close(self, page: Page) -> None:
        #self.close_url = page.url
        logger.debug(f"Page close: {page.url}")

    async def check_domcontentloaded(self, page: Page) -> None:
        #self.domcontentloaded_url = page.url
        logger.debug(f"Page domcontentloaded: {page.url}")

    async def check_load(self, page: Page) -> None:
        #self.load_url = page.url
        logger.debug(f"Page load: {page.url}")

    async def check_framenavigated(self, frame: Frame) -> None:
        #self.framenavigated_url = frame.page.url
        logger.debug(f"Page framenavigated: {frame.page.url}")

    async def check_request(self, request: Request) -> None:
        self.pending_requests.append(request)
        if request.url == SESSION_URL and request.method == 'DELETE':
            self.is_session_active = False

        if  LOG_LEVEL == 'DEBUG' and \
            request.is_navigation_request() and \
            request.method == 'POST' and \
            request.url.find('login.xfinity.com') != -1:
                logger.debug(f"Request: {request.method} {request.url}")
                logger.debug(f"Request: {request.method} {request.post_data}")
                logger.debug(f"Request: {request.method} {request.headers}")

    async def check_requestfailed(self, request: Request) -> None:
        self.pending_requests.remove(request)

    async def check_requestfinished(self, request: Request) -> None:
        self.pending_requests.remove(request)

    async def check_response(self,response: Response) -> None:
        logger.debug(f"Network Response: {response.status} {response.url}")

        if response.ok:
            request = response.request
            content_type_header = await response.header_value('content-type')
            content_length_header = await response.header_value('content-length')
            content_type = str()
            page_body = str()

            if  content_type_header is not None:
                if re.match('application/json', content_type_header):
                    content_type = 'json'

                    if content_length_header is not None and content_length_header != '0' :
                        page_body = await response.body()
                        if len(page_body) != 0:
                            logger.debug(f"Response: {response.status} {request.resource_type} {content_type} {content_length_header} {response.url}")
                            response_json = await response.json()
                    else:
                        response_json = None

            if request.is_navigation_request():
                if  LOG_LEVEL == 'DEBUG' and \
                    request.method == 'POST' and \
                    request.url.find('login.xfinity.com') != -1:
                        logger.debug(f"Response: {request.method} {request.url}")
                        logger.debug(f"Response: {response.status} {page_body}")
                        logger.debug(f"Response: {response.status} {response.headers}")

            if content_type == 'json' and response_json is None:
                if  response.url == SESSION_URL and 'x-ssm-token' in response.headers:
                    await self.check_jwt_session(response)

            if content_type == 'json' and response_json is not None:
                if response.url == PLAN_DETAILS_JSON_URL:
                    self.plan_details_data = {}
                    if 'shoppingOfferDetail' in response_json:
                        download_speed = response_json["shoppingOfferDetail"]["dynamicParameters"][1]["value"].split(" ", 1)[0]
                        upload_speed = response_json["shoppingOfferDetail"]["dynamicParameters"][0]["value"].split(" ",1)[0]
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
                if response.url == USAGE_JSON_URL:
                    self.usage_details_data = response_json
                    logger.info(f"Updating Usage Details")
                    logger.debug(f"Updating Usage Details {textwrap.shorten(json.dumps(response_json), width=120, placeholder='...')}")

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
                if response.url == DEVICE_DETAILS_JSON_URL:
                    if  'services' in response_json and \
                        len(response_json['services']['internet']['devices']) > 0 and \
                        len(response_json['services']['internet']['devices'][0]['deviceDetails']) > 0:
                            self.device_details_data = response_json['services']['internet']['devices'][0]['deviceDetails']
                            logger.info(f"Updating Device Details")
                    logger.debug(f"Updating Device Details {json.dumps(response_json)}")                


    async def get_device_details_data(self) -> None:
        if self.page.is_closed():
            self.page =  await self.get_new_page()
            await self.page.goto(DEVICE_DETAILS_URL)
            logger.info(f"Loading Device Data (URL: {parse_url(self.page.url)})")
            
            # Wait for ShimmerLoader to attach and then unattach
            await expect(self.page.locator("div#app")).to_be_attached()
            try:
                await expect(self.page.locator('div#app p[class^="connection-"]').first).to_contain_text(re.compile(r".+"))
            except Exception:
                div_app_p_count = await self.page.locator('div#app p[class^="connection-"]').count()
                if div_app_p_count > 0:
                    logger.error(f"div#app p Count: {div_app_p_count}")
                    for div_app_p in await self.page.locator('div#app p[class^="connection-"]').all():
                        logger.error(f"div#app p inner html: {div_app_p.inner_html()}")
            finally:
                if self.device_details_data is not None:
                    await self.page.wait_for_load_state('networkidle')
                    await self.page.close()

    async def get_usage_data(self) -> None:
        if self.page.is_closed():
            self.page = await self.get_new_page()
            await self.page.goto(INTERNET_SERVICE_URL)
            logger.info(f"Loading Plan & Usage Data (URL: {parse_url(self.page.url)})")
            try:
                if self.page.url == 'https://www.xfinity.com/learn/internet-service/auth':
                    await self.page.get_by_test_id('XjsPlanRow').wait_for()
                    await self.page.locator('h2.plan-row-title').wait_for()
                    await self.page.get_by_test_id('planRowDetail').nth(2).filter(has=self.page.locator(f"prism-button[href^=\"https://\"]")).wait_for()
            except Exception:
                logger.error(f"planRowDetail Count: {await self.page.get_by_test_id('planRowDetail').count()}")
                logger.error(f"planRowDetail Row 3 inner html: {await self.page.get_by_test_id('planRowDetail').nth(2).inner_html()}")
                logger.error(f"planRowDetail Row 3 text content: {await self.page.get_by_test_id('planRowDetail').nth(2).text_content()}")

            finally:
                logger.debug(f"Finished loading page (URL: {self.page.url})")
                if self.plan_details_data is not None and self.usage_details_data is not None:
                    await self.page.wait_for_load_state('networkidle')
                    await self.page.close()


    async def goto_logout(self) -> None:
        if self.page.is_closed():
            self.page = await self.get_new_page()
            await self.page.goto(LOGOUT_URL)
            if await self.page.locator('li.xc-header--avatar-menu-toggle').locator('button[aria-label="Account"]').is_visible():
                await self.page.locator('li.xc-header--avatar-menu-toggle').locator('button[aria-label="Account"]').click()
                await get_slow_down_login()

                if await self.page.locator('div.xc-header--signin-container--authenticated').locator('a.xc-header--signout-link', has_text='Sign out').is_visible():
                    await self.page.locator('div.xc-header--signin-container--authenticated').locator('a.xc-header--signout-link', has_text='Sign out').press("Enter")
                    await self.page.locator('xc-header').wait_for(state='visible')
                    while(await self.page.locator('xc-header').get_attribute('state') == "authenticated"):
                        await get_slow_down_login()
                        await self.page.locator('xc-header').wait_for(state='visible')
                    await self.page.wait_for_load_state('networkidle')
                    logger.info(f"Unloading Xfinity")
                
                elif await self.page.locator('div.xc-header--signin-container--unauthenticated').locator('a.xc-header--signin-link', has_text='Sign In').is_visible():
                    await self.page.locator('div.xc-header--signin-container--unauthenticated').locator('a.xc-header--signin-link', has_text='Sign In').press("Enter")
                    logger.info(f"Reloading Xfinity Authentication (URL: {parse_url(self.page.url)})")
                
                await get_slow_down_login()

            if not self.is_session_active:
                await self.page.wait_for_load_state('networkidle')
                await self.page.close()

    async def get_authenticated(self) -> None:
        await self.page.goto(AUTH_URL)
        logger.info(f"Loading Xfinity Authentication (URL: {parse_url(self.page.url)})")
        _title = await self.get_page_title()
        # xc-header[state="authenticated"]
        if  _title == 'Xfinity Internet: Fastest Wifi Speeds and the Best Coverage' and \
            await self.page.locator('xc-header').get_attribute('state') != "authenticated":
                await self.page.close()
                await self.goto_logout()

        _start_time = time.time()
        while(self.is_session_active is not True):
                    
            if self.plan_details_data is not None and self.usage_details_data is not None:
                self.is_session_active = True
            else:
                await self.check_for_authentication_errors()
                await self.check_authentication_form()
                await get_slow_down_login()
                
                if time.time()-_start_time > PAGE_TIMEOUT and self.is_session_active is not True:
                    _title = await self.get_page_title()
                    if _title == 'Xfinity Internet: Fastest Wifi Speeds and the Best Coverage':
                        await self.goto_logout()
                        await self.context.clear_cookies()
                        raise AssertionError(f"Login Failed: Logging out and clearing cookies")

        if self.is_session_active:
            await self.page.wait_for_load_state('networkidle')
            await self.page.close()



    async def get_authentication_form_inputs(self) -> list:
        return await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[type="text"], input[type="password"]').all()


    async def get_authentication_form_hidden_inputs(self) -> None:
        hidden_inputs = await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[type="hidden"]').all()
        if LOG_LEVEL == 'DEBUG':
            logger.debug(f"Number of hidden inputs: {len(hidden_inputs)}")
            for input in hidden_inputs:
                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")


    async def goto_authentication_page(self) -> None:
            self.page_response = await self.page.goto(AUTH_URL)
            logger.info(f"Loading Xfinity Authentication (URL: {parse_url(self.page.url)})")
            _title = await self.get_page_title()
            # xc-header[state="authenticated"]
            if  _title == 'Xfinity Internet: Fastest Wifi Speeds and the Best Coverage' and \
                await self.page.locator('xc-header').get_attribute('state') != "authenticated":
                    await self.goto_logout()


    async def get_page_title(self) -> str:
        try:
            return await self.page.title()
        except:
            return ''
        
        
    async def check_authentication_form(self):
        #self.page.wait_for_url(re.compile('https://(?:www|login)\.xfinity\.com(?:/learn/internet-service){0,1}/(?:auth|login).*'))
        
        #_title = self.page_title
        if len(self.pending_requests) == 0 and not self.is_session_active:
            logger.debug(f'pending requests {len(self.pending_requests)}')
            #await self.page.wait_for_load_state('networkidle')
            _title = await self.get_page_title()
        
            #if  self.frameattached_url == self.framenavigated_url and \
            #    re.match('https://(?:www|login)\.xfinity\.com(?:/learn/internet-service){0,1}/login',self.frameattached_url) and \
            if _title == 'Sign in to Xfinity':
                    #expect(self.page).to_have_title('Sign in to Xfinity')
                    if await self.page.locator('main').locator("form[name=\"signin\"]").is_enabled():
                        for input in await self.get_authentication_form_inputs():
                            _input_id = await input.get_attribute("id")
                            if LOG_LEVEL == 'DEBUG':
                                logger.debug(f"{self.page.url}")
                                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")
                                submit_button = await self.page.locator('main').locator("form[name=\"signin\"]").locator('button#sign_in.sc-prism-button').evaluate('el => el.outerHTML') 
                                logger.debug(f"{submit_button}")
                            
                            #<input class="input text contained body1 sc-prism-input-text" id="user" autocapitalize="off" autocomplete="username" autocorrect="off" inputmode="text" maxlength="128" name="user" placeholder="Email, mobile, or username" required="" type="text" aria-invalid="false" aria-required="true" data-ddg-inputtype="credentials.username">
                            #<input id="user" name="user" type="text" autocomplete="username" value="username" disabled="" class="hidden" data-ddg-inputtype="credentials.password.current">
                            if _input_id == 'user' and \
                                await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[name="flowStep"]').get_attribute("value") == "username":
                                if await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').is_editable():
                                    self.form_stage.append('Username')
                                    if self.username_count < 2:
                                        await self.enter_username()
                                        self.username_count += 1
                                        await self.wait_for_submit_button()
                                    else:
                                        logger.error(f"Navigated to username page for the {ordinal(self.username_count)} time. Exiting...")
                                        exit(exit_code.TOO_MANY_USERNAME.value)


                            #<input class="input icon-trailing password contained body1 sc-prism-input-text" id="passwd" autocapitalize="none" autocomplete="current-password" autocorrect="off" inputmode="text" maxlength="128" name="passwd" required="" type="password" aria-invalid="false" aria-required="true" aria-describedby="passwd-hint">
                            elif _input_id == 'passwd' and \
                                await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[name="flowStep"]').get_attribute("value") == "password":
                                if  await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').get_attribute("value") == XFINITY_USERNAME and \
                                    await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').is_disabled() and \
                                    await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#passwd').is_editable():

                                    if await self.page.locator('main').locator("form[name=\"signin\"]").locator('prism-input-text[name="passwd"]').get_attribute('invalid-message') == 'The Xfinity ID or password you entered was incorrect. Please try again.':
                                        logger.error(f"Bad password. Exiting...")
                                        exit(exit_code.BAD_PASSWORD.value)

                                    if self.password_count < 2:
                                        self.form_stage.append('Password')
                                        await self.enter_password()
                                        self.password_count += 1 
                                        await self.wait_for_submit_button()
                                    else:
                                        logger.error(f"Navigated to password page for the  {ordinal(self.password_count)} time. Exiting...")
                                        exit(exit_code.TOO_MANY_PASSWORD.value)
                                else:
                                    raise AssertionError("Password form page is missing the user id")

                            elif 'Password' in self.form_stage and _input_id == 'verificationCode':
                                await self.check_for_two_step_verification()

                    # Didn't find signin form
                    else:
                        if LOG_LEVEL == 'DEBUG':
                            for input in await self.page.locator('main').get_by_role('textbox').all():
                                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")
                        raise AssertionError("Signin form is missing")
             
    async def enter_username(self):
        # Username Section
        logger.info(f"Entering username (URL: {parse_url(self.page.url)})")
        await self.get_authentication_form_hidden_inputs()
        await get_slow_down_login()

        all_inputs = await self.get_authentication_form_inputs()
        if len(all_inputs) != 1:
            raise AssertionError("Username page: not the right amount of inputs")

        #self.session_storage = self.page.evaluate("() => JSON.stringify(sessionStorage)")

        if LOG_LEVEL == 'DEBUG':
            for input in all_inputs:
                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")

        await self.page.locator("input#user").click()
        await get_slow_down_login()
        await self.page.locator("input#user").press_sequentially(XFINITY_USERNAME, delay=150)
        await get_slow_down_login()
        await self.debug_support()
        await self.page.locator("input#user").press("Enter")
        #self.page.locator("button[type=submit]#sign_in").click()
        await self.debug_support()

    async def enter_password(self):
        # Password Section
        logger.info(f"Entering password (URL: {parse_url(self.page.url)})")
        await self.get_authentication_form_hidden_inputs()
        await get_slow_down_login()

        all_inputs = await self.get_authentication_form_inputs()
        if len(all_inputs) != 2:
                raise AssertionError("not the right amount of inputs")

        await self.page.locator("input#passwd").click()
        await get_slow_down_login()

        await expect(self.page.get_by_label('toggle password visibility')).to_be_visible()
        await self.page.locator("input#passwd").press_sequentially(XFINITY_PASSWORD, delay=175)
        await get_slow_down_login()
        await self.debug_support()

        if LOG_LEVEL == 'DEBUG':
            for input in await self.get_authentication_form_inputs():
                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")
                        
        await self.page.locator("input#passwd").press("Enter")
        #self.page.locator("button[type=submit]#sign_in").click()
        await self.debug_support()

    async def wait_for_submit_button(self) -> None:
        try:
            _submit_button = self.page.locator('main').locator("form[name=\"signin\"]").locator('button#sign_in.sc-prism-button')
            #await expect(_submit_button.locator('div.loading-spinner')).to_be_attached()
            await _submit_button.locator('div.loading-spinner').wait_for(state='visible')
            logger.debug(f"{await _submit_button.evaluate('el => el.outerHTML')}")
            await _submit_button.locator('div.loading-spinner').wait_for(state='detached')
            #self.page.wait_for_load_state('domcontentloaded')
        finally:
            return


    async def check_for_two_step_verification(self):
        # Check for Two Step Verification
        logger.info(f"Two Step Verification Check: Page Title {await self.get_page_title()}")
        logger.info(f"Two Step Verification Check: Page Url {self.page.url}")
        await self.get_authentication_form_hidden_inputs()
        
        for input in await self.get_authentication_form_inputs():
            logger.error(f"{await input.evaluate('el => el.outerHTML')}")
            if re.search('id="user"',await input.evaluate('el => el.outerHTML')):
                raise AssertionError("Password form submission failed")

            if  re.search('id="verificationCode"',await input.evaluate('el => el.outerHTML')) and \
                await self.page.locator("input#verificationCode").is_enabled():
                    two_step_verification_handler()

    async def check_for_authentication_errors(self):
        if await self.get_page_title() == 'Access Denied':
            if run_playwright.statistics['attempt_number'] > 3:
                logger.error(f"{ordinal(run_playwright.statistics['attempt_number'])} Akamai Access Denied error!!")
                logger.error(f"Lets sleep for 6 hours and then try again")
                akamai_sleep()
            else:
                raise AssertionError(f"{ordinal(run_playwright.statistics['attempt_number'])} Akamai Access Denied error!!")


    async def run(self) -> None:
        """
        Main business loop.
            * Go to Usage URL
            * Login if needed
            * Process usage data for HA Sensor
            * Push usage to HA Sensor

        Returns: None
        """
        await self.start()

        await self.get_authenticated()
        
        await self.get_usage_data()

        # If we have the plan and usage data, success and lets process it
        if self.plan_details_data is not None and self.usage_details_data is not None:
            
            # If MQTT is enable attempt to gather real cable modem details
            if is_mqtt_available() and bool(mqtt_client.mqtt_device_details_dict) is False:
                await self.get_device_details_data()
                mqtt_client.mqtt_device_details_dict = self.device_details_data

            # Now compile the usage data for the sensor
            await self.process_usage_json(self.usage_details_data)

            #if  self.is_session_active and self.usage_data is not None:
            if self.usage_data is not None and is_mqtt_available() is False:
                logger.debug(f"Sensor API Url: {SENSOR_URL}")
                await self.update_ha_sensor()
                await self.update_sensor_file()

        # Plan and usage data is missing throw an Assertion to cause retry
        else:
            await self.debug_support()
            raise AssertionError("Usage page did not load correctly, missing usage data")
        

# Retry
# Stop retrying after 15 attempts
# Wait exponentially
#
@retry(stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True)
async def run_playwright() -> None:
    """
        * Start Playwright
        * Initialize XfinityUsage class
        * usage.run() to get usage data and push usage to HA Sensor
        * Stop Playwright

    Returns: None
    """
    if run_playwright.statistics['attempt_number'] > 1:
        logger.warning(f"{ordinal(run_playwright.statistics['attempt_number'] - 1)} retry")

    async with async_playwright() as playwright:
        usage = XfinityUsage(playwright)
        try:
            await usage.run()
            
            if is_mqtt_available() and mqtt_client.is_connected_mqtt():
                mqtt_client.publish_mqtt(usage.usage_data)

        finally:
            await usage.done()



async def main():
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


    """
        * run_playwright does all the work
        * sleep for POLLING_RATE

    Returns: None
    """
    logger.info(f"Xfinity Internet Usage Starting")
    while True:
        try:
            await run_playwright()
            
            # Only allow one run of the script
            if DEBUG_SUPPORT: exit(exit_code.DEBUG_SUPPORT.value)

            exit(exit_code.SUCCESS.value)

        except BaseException as e:
            if (type(e) == SystemExit) and \
                (e.code == exit_code.TOO_MANY_USERNAME.value or \
                e.code == exit_code.TOO_MANY_PASSWORD.value):
                        # Remove browser profile path to clean out cookies and cache
                        profile_path = '/config/profile*'
                        directories = glob.glob(profile_path)
                        for directory in directories:
                            if Path(directory).exists() and Path(directory).is_dir(): shutil.rmtree(directory)

            if is_mqtt_available():
                mqtt_client.disconnect_mqtt()

            if type(e) == SystemExit:
                exit(e.code)
            else: 
                exit(exit_code.MAIN_EXCEPTION.value)


if __name__ == '__main__':
        # Setup variables from Addon Configuration
    if XFINITY_PASSWORD is None or XFINITY_USERNAME is None:
        logger.error("No Username or Password specified")
        exit(exit_code.MISSING_LOGIN_CONFIG.value)

    xfinity_block_list = []
    for block_list in os.popen(f"curl -s --connect-timeout {PAGE_TIMEOUT} https://easylist.to/easylist/easyprivacy.txt | grep '^||.*xfinity' | sed -e 's/^||//' -e 's/\^//'"):
        xfinity_block_list.append(block_list.rstrip())

    if is_mqtt_available():
        # Initialize and connect to MQTT server
        mqtt_client = XfinityMqtt()
    else:
        mqtt_client = None

    asyncio.run(main())
import aiohttp
import asyncio
import base64
import colorlog
import fnmatch
import glob
import hashlib
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
import pycurl
import certifi

from io import BytesIO
from datetime import datetime
from enum import Enum
import requests.adapters
from tenacity import stop_after_attempt,  wait_exponential, retry, before_sleep_log
from time import sleep
from paho.mqtt import client as mqtt
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
# Browser mode
HEADLESS = json.loads(os.environ.get('HEADLESS', 'true').lower()) # Convert HEADLESS string into boolean

# Login slow variables
SLOW_DOWN_MIN = os.environ.get('SLOW_DOWN_MIN', 0.5)
SLOW_DOWN_MAX = os.environ.get('SLOW_DOWN_MAX', 1.2)
SLOW_DOWN_LOGIN = True

#Randomize User Agent variables
ANDROID_MIN_VERSION = os.environ.get('ANDROID_MIN_VERSION', 10)
ANDROID_MAX_VERSION = os.environ.get('ANDROID_MAX_VERSION', 10)
FIREFOX_MIN_VERSION = os.environ.get('FIREFOX_MIN_VERSION', 120)
FIREFOX_MAX_VERSION = os.environ.get('FIREFOX_MAX_VERSION', 120)

# GLOBAL URLS
VIEW_USAGE_URL = 'https://customer.xfinity.com/#/devices#usage'
VIEW_WIFI_URL = 'https://customer.xfinity.com/settings/wifi'
INTERNET_SERVICE_URL = 'https://www.xfinity.com/learn/internet-service/auth'
#AUTH_URL = 'https://content.xfinity.com/securelogin/cima?sc_site=xfinity-learn-ui&continue=https://www.xfinity.com/auth'
AUTH_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/authorize?redirect_uri=xfinitydigitalhome%3A%2F%2Fauth&client_id=xfinity-android-application&response_type=code&prompt=select_account&state=c4Za0xlL2JcZsQpbidgkeQ&scope=profile&code_challenge=OA8IddNHWFfrCAZGp-kKRa4WGEDvTYoJTyA5Sn9YKyE&code_challenge_method=S256&activity_id=1d58b6e3-99c9-485e-b2dd-8180bfcf75ae&active_x1_account_count=true&rm_hint=true&partner_id=comcast&mso_partner_hint=true'
LOGIN_URL = 'https://login.xfinity.com/login'
LOGOUT_URL = 'https://www.xfinity.com/overview'
USAGE_JSON_URL = 'https://api.sc.xfinity.com/session/csp/selfhelp/account/me/services/internet/usage'
PLAN_DETAILS_JSON_URL = 'https://api.sc.xfinity.com/session/plan'
DEVICE_DETAILS_URL = 'https://www.xfinity.com/support/status'
DEVICE_DETAILS_JSON_URL = 'https://api.sc.xfinity.com/devices/status'
SESSION_URL = 'https://api.sc.xfinity.com/session'
XFINITY_START_URL = 'https://oauth.xfinity.com/oauth/sp-logout?client_id=shoplearn-web'
#AUTH_PAGE_TITLE = 'Internet, TV, Phone, Smart Home and Security - Xfinity by Comcast'
AUTH_PAGE_TITLE = 'Discovery Hub - News & Technology'
OAUTH_CODE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code'
OAUTH_TOKEN_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/token'
GRAPHQL_URL = 'https://gw.api.dh.comcast.com/galileo/graphql'

# Xfinity authentication
XFINITY_USERNAME = os.environ.get('XFINITY_USERNAME', None)
XFINITY_PASSWORD = os.environ.get('XFINITY_PASSWORD', None)

# Script polling rate
BYPASS = int(os.environ.get('BYPASS',0))
POLLING_RATE = float(int(os.environ.get('POLLING_RATE', 0)))

# Force profile cleanup during startup
PROFILE_CLEANUP = json.loads(os.environ.get('PROFILE_CLEANUP', 'false').lower()) # Convert PROFILE_CLEANUP string into boolean

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


with sync_playwright() as p:
    browser = p.chromium.launch(
            headless=True,
        )
    page = browser.new_page()
    stealth_sync(page)
    page.goto("https://bot.sannysoft.com/")
    page.screenshot(path=f"example_with_stealth.png", full_page=True)
    browser.close()

mytime = time.gmtime(1735927990187 / 1000)
mytime_string = time.strftime("%Y-%m-%d %H:%M:%S", mytime)


print(mytime_string)






async def main():

    def generate_code_challenge(code_verifier):
        """Generates a code challenge from a code verifier."""

        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')
        return code_challenge

    def generate_code_verifier():
        """Generates a random code verifier."""

        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')

    print(" Test", bool(''))
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    print("Code Verifier:", code_verifier)
    print("Code Challenge:", code_challenge)

    response_url = 'https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code?code=0.ac.w2.FOXxDw&state=eyJlbmMiOiJBMTI4R0NNIiwiYWxnIjoiUlNBLU9BRVAtMjU2In0.lWsSEgXUQwGYKHow4MbcKF67m9F3grat_NLz7FiUAUYip7J3JRebAnFKHVpfXzFlf3F3WUkF9IFMRrwx8qkzxED707--ZNK9cfrF4F1p5nL_rZIePxL41do29B1mFMVkJdqDM7RUy6k9VdWtglR5p89vtjib7dikP2oy6FKJ0zgafXkaxD0ROSPJ7oOzEtE1d6LIxuYsoJXu-FX9J5XDaJwT9hGHKs2IXJjluxGI6A_xGg79ICUGrdZb-uBC7CWp574PU650BtF2BSyzIhF7fIO4Bk3EBLleErhAUxNk-Szm9DOWPNVf6X6keWdfqIq6gwhCAMug4e3dpAcEzvWr3w.Fe5Ydm5V445Gveel.ba-CUchdTlrdBI_zuM91zO3kfkP_J7NchiCOuMHsbEr__Gd7WxwXW6N1y3cbSRrdnPVI276xOD1YEQiCQwa81KNekxRC40aqXmSISPdqQsgy9ZUuhdytyblnknm-n9E98ibTdY3cGskwiZtqieEU7qSWDOL91HX3jaLWwcNElejTOTj0WNuO1o5qpNHmkyxNwmZmDqepg9tlSTImRHMG44LU7lIMBufh0Zvv6l2kEX0ZDTk3314voZAxfHHsr3FfRYTOA_Ub-ZtHFxIEV_sg9e2e7juG5UeQ8pbMm84_uQVcwLF6513bU_28_jsCVBlFB2uhgEUEvGyDhNJYZTM0Rg8st7ILsSMVcKHDPhFULg4s0KGCv8M9nqa8cl3wkSUGM-LE0Pz1NR_JxdjFPZrW6qwQPgvQesKY28ImnECg-ONKc1Rpvva0udflZve80KsdZ6m8ynCFttEdxTXymzlRSyhMprM-0XXY1_75MOxKDw8fq0m23Ao0fdGRwLlx64y1COFKr6sUCNqGJjGGIhHKnFxoOfkpUkuLemcYmTh2_-JslneFEPGUd-UcQAijcO9gDFfrcj6hUrMw1uXO-QU3e320biBf8CKLTgtLENYur0LcMmmrVz5HujVoxSsZO6cKSbvN9P9nD3WPutDd0pyMTrFBdgJ4905HMSDiW3zOD_grNYumz_OmUB4qhHpZ5IxYnxO9wpKMSLER5fMzj7nF-1qEw6_JmrNN6ULHkL4fMlfhHcf0jhSEqVaHCH4QtXCOmujbKyK1GIOi3o35mQ.qFR3MQXgevwkTR2UP-UqdQ'
    oauth_hostname = urllib.parse.urlsplit(OAUTH_CODE_URL).hostname
    oauth_path =  urllib.parse.urlsplit(OAUTH_CODE_URL).path
    if re.search(r"^"+OAUTH_CODE_URL, response_url):
        oauth_code_urlparse = urllib.parse.urlparse(response_url)
        oauth_code_params = urllib.parse.parse_qs(oauth_code_urlparse.query)
        if oauth_code_params.get('code') and oauth_code_params.get('state'):
            print(f"OAUTH_CODE_URL: {response_url}")

    location = 'xfinitydigitalhome://auth?state=c4Za0xlL2JcZsQpbidgkeQ&activity_id=f26afa7a-cdcd-11ef-aa46-a2732dd3a7e2&code=1ea8e5fd1977473593a7f8b7cb9e6265'
    location_parse = urllib.parse.urlparse(location)

    query_params = urllib.parse.parse_qs(location_parse.query)
    print("code:", query_params['code'])

    try:
        # Configure retries
        #adapter = requests.adapters.HTTPAdapter()
        
        #s = requests.Session()
        #s.mount('xfinitydigitalhome://',adapter)
        #code_req = s.get('https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code?code=0.ac.w2.FOXxDw&state=eyJlbmMiOiJBMTI4R0NNIiwiYWxnIjoiUlNBLU9BRVAtMjU2In0.lWsSEgXUQwGYKHow4MbcKF67m9F3grat_NLz7FiUAUYip7J3JRebAnFKHVpfXzFlf3F3WUkF9IFMRrwx8qkzxED707--ZNK9cfrF4F1p5nL_rZIePxL41do29B1mFMVkJdqDM7RUy6k9VdWtglR5p89vtjib7dikP2oy6FKJ0zgafXkaxD0ROSPJ7oOzEtE1d6LIxuYsoJXu-FX9J5XDaJwT9hGHKs2IXJjluxGI6A_xGg79ICUGrdZb-uBC7CWp574PU650BtF2BSyzIhF7fIO4Bk3EBLleErhAUxNk-Szm9DOWPNVf6X6keWdfqIq6gwhCAMug4e3dpAcEzvWr3w.Fe5Ydm5V445Gveel.ba-CUchdTlrdBI_zuM91zO3kfkP_J7NchiCOuMHsbEr__Gd7WxwXW6N1y3cbSRrdnPVI276xOD1YEQiCQwa81KNekxRC40aqXmSISPdqQsgy9ZUuhdytyblnknm-n9E98ibTdY3cGskwiZtqieEU7qSWDOL91HX3jaLWwcNElejTOTj0WNuO1o5qpNHmkyxNwmZmDqepg9tlSTImRHMG44LU7lIMBufh0Zvv6l2kEX0ZDTk3314voZAxfHHsr3FfRYTOA_Ub-ZtHFxIEV_sg9e2e7juG5UeQ8pbMm84_uQVcwLF6513bU_28_jsCVBlFB2uhgEUEvGyDhNJYZTM0Rg8st7ILsSMVcKHDPhFULg4s0KGCv8M9nqa8cl3wkSUGM-LE0Pz1NR_JxdjFPZrW6qwQPgvQesKY28ImnECg-ONKc1Rpvva0udflZve80KsdZ6m8ynCFttEdxTXymzlRSyhMprM-0XXY1_75MOxKDw8fq0m23Ao0fdGRwLlx64y1COFKr6sUCNqGJjGGIhHKnFxoOfkpUkuLemcYmTh2_-JslneFEPGUd-UcQAijcO9gDFfrcj6hUrMw1uXO-QU3e320biBf8CKLTgtLENYur0LcMmmrVz5HujVoxSsZO6cKSbvN9P9nD3WPutDd0pyMTrFBdgJ4905HMSDiW3zOD_grNYumz_OmUB4qhHpZ5IxYnxO9wpKMSLER5fMzj7nF-1qEw6_JmrNN6ULHkL4fMlfhHcf0jhSEqVaHCH4QtXCOmujbKyK1GIOi3o35mQ.qFR3MQXgevwkTR2UP-UqdQ')

        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=False) as response:
                location = response.headers.get('location').replace('xfinitydigitalhome://', 'https://')
                location = 'https://auth?state=c4Za0xlL2JcZsQpbidgkeQ&activity_id=1d58b6e3-99c9-485e-b2dd-8180bfcf75ae&code=ffe4f2328e3b46a6aae594d41f6897c7'
                location_parse = urllib.parse.urlparse(location)

                query_params = urllib.parse.parse_qs(location_parse.query)
                print("Status:", response.status)
                print("Content-type:", response.headers['content-type'])

        headers = {}
        def header_function(header_line):
            # HTTP standard specifies that headers are encoded in iso-8859-1.
            # On Python 2, decoding step can be skipped.
            # On Python 3, decoding step is required.
            header_line = header_line.decode('iso-8859-1')

            # Header lines include the first status line (HTTP/1.x ...).
            # We are going to ignore all lines that don't have a colon in them.
            # This will botch headers that are split on multiple lines...
            if ':' not in header_line:
                return

            # Break the header line into header name and value.
            name, value = header_line.split(':', 1)

            # Remove whitespace that may be present.
            # Header lines include the trailing newline, and there may be whitespace
            # around the colon.
            name = name.strip()
            value = value.strip()

            # Header names are case insensitive.
            # Lowercase name here.
            name = name.lower()

            # Now we can actually record the header name and value.
            # Note: this only works when headers are not duplicated, see below.
            headers[name] = value
            
        buffer = BytesIO()
        c = pycurl.Curl()
        c.setopt(c.URL, 'https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code?code=0.ac.w2.FOXxDw&state=eyJlbmMiOiJBMTI4R0NNIiwiYWxnIjoiUlNBLU9BRVAtMjU2In0.lWsSEgXUQwGYKHow4MbcKF67m9F3grat_NLz7FiUAUYip7J3JRebAnFKHVpfXzFlf3F3WUkF9IFMRrwx8qkzxED707--ZNK9cfrF4F1p5nL_rZIePxL41do29B1mFMVkJdqDM7RUy6k9VdWtglR5p89vtjib7dikP2oy6FKJ0zgafXkaxD0ROSPJ7oOzEtE1d6LIxuYsoJXu-FX9J5XDaJwT9hGHKs2IXJjluxGI6A_xGg79ICUGrdZb-uBC7CWp574PU650BtF2BSyzIhF7fIO4Bk3EBLleErhAUxNk-Szm9DOWPNVf6X6keWdfqIq6gwhCAMug4e3dpAcEzvWr3w.Fe5Ydm5V445Gveel.ba-CUchdTlrdBI_zuM91zO3kfkP_J7NchiCOuMHsbEr__Gd7WxwXW6N1y3cbSRrdnPVI276xOD1YEQiCQwa81KNekxRC40aqXmSISPdqQsgy9ZUuhdytyblnknm-n9E98ibTdY3cGskwiZtqieEU7qSWDOL91HX3jaLWwcNElejTOTj0WNuO1o5qpNHmkyxNwmZmDqepg9tlSTImRHMG44LU7lIMBufh0Zvv6l2kEX0ZDTk3314voZAxfHHsr3FfRYTOA_Ub-ZtHFxIEV_sg9e2e7juG5UeQ8pbMm84_uQVcwLF6513bU_28_jsCVBlFB2uhgEUEvGyDhNJYZTM0Rg8st7ILsSMVcKHDPhFULg4s0KGCv8M9nqa8cl3wkSUGM-LE0Pz1NR_JxdjFPZrW6qwQPgvQesKY28ImnECg-ONKc1Rpvva0udflZve80KsdZ6m8ynCFttEdxTXymzlRSyhMprM-0XXY1_75MOxKDw8fq0m23Ao0fdGRwLlx64y1COFKr6sUCNqGJjGGIhHKnFxoOfkpUkuLemcYmTh2_-JslneFEPGUd-UcQAijcO9gDFfrcj6hUrMw1uXO-QU3e320biBf8CKLTgtLENYur0LcMmmrVz5HujVoxSsZO6cKSbvN9P9nD3WPutDd0pyMTrFBdgJ4905HMSDiW3zOD_grNYumz_OmUB4qhHpZ5IxYnxO9wpKMSLER5fMzj7nF-1qEw6_JmrNN6ULHkL4fMlfhHcf0jhSEqVaHCH4QtXCOmujbKyK1GIOi3o35mQ.qFR3MQXgevwkTR2UP-UqdQ')
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(c.CAINFO, certifi.where())
        c.setopt(c.VERBOSE, True)

        # Set our header function.
        c.setopt(c.HEADERFUNCTION, header_function)
        c.perform()
        c.close()

        if 'location' in headers:
            location = headers['location']
            print(location)
        body = buffer.getvalue()
        print(body.decode('iso-8859-1'))
    except Exception as e:
        ev = e

asyncio.run(main())       